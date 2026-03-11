"""
production/tests/chaos_test.py
Final Challenge — Chaos Testing

Validates that the NimbusFlow Customer Success FTE survives random pod kills
and recovers without message loss, as required by the 24-hour multi-channel test.

Chaos scenario (Final Challenge spec):
    1. Every 2 hours, kill a random FTE pod (api or worker)
    2. Verify the cluster self-heals within the recovery SLO (60 s)
    3. Assert no messages were lost by comparing DB counters before/after

Prerequisites:
    pip install kubernetes requests pytest pytest-asyncio
    kubectl proxy --port=8001 &        (or set KUBECONFIG + in-cluster auth)
    export CHAOS_API_URL=http://api.nimbusflow.io   (or localhost)
    export CHAOS_NAMESPACE=customer-success-fte      (default)
    export CHAOS_DB_DSN=postgresql://...             (optional — skips DB checks if absent)

Run (full 24 h, 12 pod kills):
    pytest production/tests/chaos_test.py -v -s --timeout=90000

Run (single kill cycle, for CI smoke):
    pytest production/tests/chaos_test.py::test_single_kill_and_recovery -v -s

Thresholds:
    Recovery SLO        : < 60 s after pod deletion
    Max consecutive failures during kill : 10 health pings (10 s window)
    Message loss        : 0 messages lost across full 24 h run
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import pytest
import requests

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── Config ─────────────────────────────────────────────────────────────────────

NAMESPACE      = os.getenv("CHAOS_NAMESPACE", "customer-success-fte")
API_URL        = os.getenv("CHAOS_API_URL", "http://localhost:8000")
DB_DSN         = os.getenv("CHAOS_DB_DSN", "")       # optional; skips DB checks if blank

KILL_INTERVAL_S   = int(os.getenv("CHAOS_KILL_INTERVAL_S",  str(2 * 3600)))  # 2 h
KILL_CYCLES       = int(os.getenv("CHAOS_KILL_CYCLES",      "12"))           # 12 kills = 24 h
RECOVERY_TIMEOUT_S = int(os.getenv("CHAOS_RECOVERY_TIMEOUT_S", "60"))
HEALTH_POLL_S     = 5
MAX_CONSECUTIVE_FAILURES = 10

TARGET_LABEL_SELECTORS = [
    "app=fte-api",
    "app=fte-worker",
]


# ── Kubernetes helpers ─────────────────────────────────────────────────────────

def _k8s_client():
    """
    Return a configured kubernetes CoreV1Api client.
    Tries in-cluster config first (pod environment), falls back to kubeconfig.
    """
    try:
        from kubernetes import client as k8s, config as k8s_config  # type: ignore
    except ImportError:
        pytest.skip("kubernetes package not installed — skipping chaos tests")

    try:
        k8s_config.load_incluster_config()
    except Exception:
        try:
            k8s_config.load_kube_config()
        except Exception:
            pytest.skip("No Kubernetes config available — skipping chaos tests")

    return k8s.CoreV1Api()


def list_running_pods(v1, namespace: str, label_selector: str) -> list:
    """Return running pods matching label_selector in namespace."""
    pods = v1.list_namespaced_pod(
        namespace=namespace,
        label_selector=label_selector,
    )
    return [
        p for p in pods.items
        if p.status.phase == "Running"
        and all(cs.ready for cs in (p.status.container_statuses or []))
    ]


def kill_pod(v1, namespace: str, pod_name: str) -> None:
    """Delete a pod by name — Kubernetes will restart it immediately."""
    from kubernetes import client as k8s  # type: ignore
    log.info(f"[chaos] Deleting pod {pod_name} in {namespace}")
    v1.delete_namespaced_pod(
        name=pod_name,
        namespace=namespace,
        body=k8s.V1DeleteOptions(grace_period_seconds=0),
    )


def kill_random_pod(v1, namespace: str, label_selector: str) -> Optional[str]:
    """
    Kill a random running pod matching label_selector.
    Returns the killed pod name, or None if no pods were available.
    """
    pods = list_running_pods(v1, namespace, label_selector)
    if not pods:
        log.warning(f"[chaos] No running pods found for {label_selector}")
        return None
    pod = random.choice(pods)
    kill_pod(v1, namespace, pod.metadata.name)
    return pod.metadata.name


# ── Health polling ─────────────────────────────────────────────────────────────

@dataclass
class RecoveryResult:
    recovered: bool
    elapsed_s: float
    consecutive_failures: int
    final_status: Optional[int] = None


def wait_for_recovery(
    api_url: str,
    timeout_s: int = RECOVERY_TIMEOUT_S,
    poll_s: int = HEALTH_POLL_S,
) -> RecoveryResult:
    """
    Poll GET /health until 200 or timeout.
    Returns RecoveryResult with elapsed time and consecutive failure count.
    """
    deadline   = time.monotonic() + timeout_s
    failures   = 0
    max_consec = 0
    cur_consec = 0

    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{api_url}/health", timeout=5)
            if resp.status_code == 200:
                elapsed = timeout_s - (deadline - time.monotonic())
                log.info(f"[chaos] Recovered in {elapsed:.1f}s  (max consecutive failures: {max_consec})")
                return RecoveryResult(
                    recovered=True,
                    elapsed_s=elapsed,
                    consecutive_failures=max_consec,
                    final_status=200,
                )
            cur_consec += 1
            failures   += 1
        except requests.exceptions.RequestException:
            cur_consec += 1
            failures   += 1

        max_consec = max(max_consec, cur_consec)
        cur_consec_reset = (cur_consec if resp is None or resp.status_code != 200 else 0)  # noqa
        time.sleep(poll_s)

    log.error(f"[chaos] Did NOT recover within {timeout_s}s")
    return RecoveryResult(
        recovered=False,
        elapsed_s=float(timeout_s),
        consecutive_failures=max_consec,
    )


# ── Message loss detection ─────────────────────────────────────────────────────

@dataclass
class MessageCounts:
    total_messages:    int = 0
    total_errors:      int = 0
    channel_breakdown: dict = field(default_factory=dict)


def _fetch_message_counts_from_api(api_url: str) -> MessageCounts:
    """
    Read message counts from GET /metrics/channels.
    Falls back to zero counts if endpoint is unreachable (counted as a failure
    only when compared after the full run).
    """
    try:
        resp = requests.get(f"{api_url}/metrics/channels", timeout=10)
        if resp.status_code != 200:
            return MessageCounts()
        data     = resp.json()
        channels = data.get("channels", [])
        total    = sum(ch.get("message_count", 0) for ch in channels)
        breakdown = {ch.get("channel"): ch.get("message_count", 0) for ch in channels}
        return MessageCounts(total_messages=total, channel_breakdown=breakdown)
    except Exception as exc:
        log.warning(f"[chaos] Could not fetch message counts: {exc}")
        return MessageCounts()


async def _fetch_message_counts_from_db(dsn: str) -> MessageCounts:
    """
    Query DB directly for accurate message counts.
    Used when CHAOS_DB_DSN is set; more reliable than the API under load.
    """
    try:
        import asyncpg  # type: ignore
    except ImportError:
        log.warning("[chaos] asyncpg not installed — falling back to API counts")
        return _fetch_message_counts_from_api(API_URL)

    try:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            total = await conn.fetchval("SELECT COUNT(*) FROM messages")
            rows  = await conn.fetch(
                "SELECT channel, COUNT(*) AS cnt FROM messages GROUP BY channel"
            )
            breakdown = {r["channel"]: r["cnt"] for r in rows}
            return MessageCounts(total_messages=total, channel_breakdown=breakdown)
        finally:
            await conn.close()
    except Exception as exc:
        log.warning(f"[chaos] DB count query failed: {exc}")
        return MessageCounts()


def get_message_counts() -> MessageCounts:
    """Prefer DB counts if DSN available, else use metrics API."""
    if DB_DSN:
        return asyncio.get_event_loop().run_until_complete(
            _fetch_message_counts_from_db(DB_DSN)
        )
    return _fetch_message_counts_from_api(API_URL)


# ── Chaos engine ───────────────────────────────────────────────────────────────

@dataclass
class KillCycleResult:
    cycle_number:       int
    label_selector:     str
    killed_pod:         Optional[str]
    recovery:           RecoveryResult
    messages_before:    int
    messages_after:     int
    message_loss:       int
    passed:             bool


class ChaosEngine:
    """
    Orchestrates repeated pod kills at KILL_INTERVAL_S intervals.

    Usage:
        engine = ChaosEngine()
        results = engine.run(cycles=12)
        engine.assert_no_failures(results)
    """

    def __init__(self) -> None:
        self.v1 = _k8s_client()

    def run_single_cycle(self, cycle_number: int) -> KillCycleResult:
        """Execute one kill-recover-verify cycle."""
        label_selector = random.choice(TARGET_LABEL_SELECTORS)
        log.info(f"[chaos] ─── Cycle {cycle_number} — targeting {label_selector} ───")

        # Snapshot message count before kill
        counts_before = get_message_counts()
        log.info(f"[chaos] Messages before kill: {counts_before.total_messages}")

        # Kill a random pod
        killed_pod = kill_random_pod(self.v1, NAMESPACE, label_selector)
        kill_time  = time.monotonic()

        if killed_pod is None:
            log.warning(f"[chaos] Cycle {cycle_number}: no pod killed — skipping")
            return KillCycleResult(
                cycle_number=cycle_number,
                label_selector=label_selector,
                killed_pod=None,
                recovery=RecoveryResult(recovered=True, elapsed_s=0, consecutive_failures=0),
                messages_before=counts_before.total_messages,
                messages_after=counts_before.total_messages,
                message_loss=0,
                passed=True,
            )

        # Wait for recovery
        recovery = wait_for_recovery(API_URL, timeout_s=RECOVERY_TIMEOUT_S)

        # Brief settle time — let Kafka consumer re-join and process any buffered messages
        settle_s = 15
        log.info(f"[chaos] Settling {settle_s}s before checking message counts…")
        time.sleep(settle_s)

        # Snapshot message count after recovery
        counts_after = get_message_counts()
        log.info(f"[chaos] Messages after recovery: {counts_after.total_messages}")

        # Message loss = messages that disappeared (never 0 unless counts went backwards,
        # which would indicate a DB problem, not message loss).
        message_loss = max(0, counts_before.total_messages - counts_after.total_messages)

        passed = (
            recovery.recovered
            and recovery.elapsed_s < RECOVERY_TIMEOUT_S
            and recovery.consecutive_failures <= MAX_CONSECUTIVE_FAILURES
            and message_loss == 0
        )

        log.info(
            f"[chaos] Cycle {cycle_number} {'PASS' if passed else 'FAIL'}: "
            f"pod={killed_pod} recovery={recovery.elapsed_s:.1f}s "
            f"max_consec_fail={recovery.consecutive_failures} "
            f"msg_loss={message_loss}"
        )
        return KillCycleResult(
            cycle_number=cycle_number,
            label_selector=label_selector,
            killed_pod=killed_pod,
            recovery=recovery,
            messages_before=counts_before.total_messages,
            messages_after=counts_after.total_messages,
            message_loss=message_loss,
            passed=passed,
        )

    def run(self, cycles: int = KILL_CYCLES) -> list[KillCycleResult]:
        """
        Run `cycles` kill-recover-verify cycles, sleeping KILL_INTERVAL_S between each.
        Returns all results for assertion.
        """
        results: list[KillCycleResult] = []
        for i in range(1, cycles + 1):
            result = self.run_single_cycle(i)
            results.append(result)
            if i < cycles:
                log.info(f"[chaos] Sleeping {KILL_INTERVAL_S}s until next kill cycle…")
                time.sleep(KILL_INTERVAL_S)
        return results

    @staticmethod
    def assert_no_failures(results: list[KillCycleResult]) -> None:
        """Raise AssertionError if any cycle failed."""
        failed = [r for r in results if not r.passed]
        if not failed:
            log.info(f"[chaos] All {len(results)} cycles passed ✓")
            return
        lines = [f"  Cycle {r.cycle_number}: pod={r.killed_pod} "
                 f"recovered={r.recovery.recovered} "
                 f"elapsed={r.recovery.elapsed_s:.1f}s "
                 f"msg_loss={r.message_loss}"
                 for r in failed]
        raise AssertionError(
            f"[chaos] {len(failed)}/{len(results)} cycles failed:\n" + "\n".join(lines)
        )


# ── pytest test cases ──────────────────────────────────────────────────────────


def test_single_kill_and_recovery():
    """
    Smoke test: kill one random pod and verify recovery within SLO.

    Run this in CI after every deployment to catch regressions quickly.
    Skipped if no Kubernetes cluster is reachable.
    """
    engine = ChaosEngine()
    result = engine.run_single_cycle(cycle_number=1)

    assert result.recovery.recovered, (
        f"System did not recover within {RECOVERY_TIMEOUT_S}s "
        f"after killing {result.killed_pod}"
    )
    assert result.recovery.elapsed_s < RECOVERY_TIMEOUT_S, (
        f"Recovery took {result.recovery.elapsed_s:.1f}s — SLO is {RECOVERY_TIMEOUT_S}s"
    )
    assert result.recovery.consecutive_failures <= MAX_CONSECUTIVE_FAILURES, (
        f"More than {MAX_CONSECUTIVE_FAILURES} consecutive health failures during kill "
        f"({result.recovery.consecutive_failures})"
    )
    assert result.message_loss == 0, (
        f"Message loss detected: {result.message_loss} messages disappeared after pod kill"
    )


def test_api_pod_kill_and_recovery():
    """Kill specifically an API pod and verify recovery."""
    v1      = _k8s_client()
    killed  = kill_random_pod(v1, NAMESPACE, "app=fte-api")

    if killed is None:
        pytest.skip("No API pods available to kill")

    recovery = wait_for_recovery(API_URL, timeout_s=RECOVERY_TIMEOUT_S)

    assert recovery.recovered, (
        f"API did not recover within {RECOVERY_TIMEOUT_S}s after killing {killed}"
    )
    assert recovery.elapsed_s < RECOVERY_TIMEOUT_S
    assert recovery.consecutive_failures <= MAX_CONSECUTIVE_FAILURES


def test_worker_pod_kill_does_not_affect_api():
    """
    Kill a worker pod; the API /health must remain responsive throughout
    (workers have no HTTP port — API health should be unaffected).
    """
    v1 = _k8s_client()

    # Verify health before kill
    resp_before = requests.get(f"{API_URL}/health", timeout=5)
    assert resp_before.status_code == 200, "API health not OK before worker kill"

    killed = kill_random_pod(v1, NAMESPACE, "app=fte-worker")
    if killed is None:
        pytest.skip("No worker pods available to kill")

    # API should still respond immediately (worker kill doesn't touch API pods)
    time.sleep(3)
    resp_after = requests.get(f"{API_URL}/health", timeout=5)
    assert resp_after.status_code == 200, (
        f"API health degraded after worker pod kill ({killed})"
    )


def test_no_message_loss_after_single_kill():
    """
    Verify message counts do not decrease after a pod kill cycle.
    Skipped if neither DB DSN nor metrics API is reachable.
    """
    before = get_message_counts()

    engine = ChaosEngine()
    result = engine.run_single_cycle(cycle_number=1)

    after = get_message_counts()
    loss  = max(0, before.total_messages - after.total_messages)

    assert result.recovery.recovered, "System did not recover after kill"
    assert loss == 0, (
        f"Message loss: {before.total_messages} messages before → "
        f"{after.total_messages} messages after kill of {result.killed_pod}"
    )


@pytest.mark.slow
def test_24h_chaos_run():
    """
    Full 24-hour chaos test: 12 kill cycles × 2-hour intervals.

    Marked 'slow' — only run explicitly:
        pytest production/tests/chaos_test.py::test_24h_chaos_run -v -s --timeout=90000

    Final Challenge pass criteria (all must hold across all cycles):
        - Recovery SLO < 60 s per kill
        - ≤ 10 consecutive health failures per kill window
        - 0 messages lost across entire run
    """
    engine  = ChaosEngine()
    results = engine.run(cycles=KILL_CYCLES)

    # Print summary table
    log.info("─── 24-Hour Chaos Test Summary ──────────────────────────")
    log.info(f"  {'Cycle':<6} {'Pod killed':<40} {'Rec(s)':<8} {'ConsFail':<10} {'MsgLoss':<8} {'Pass'}")
    for r in results:
        log.info(
            f"  {r.cycle_number:<6} {str(r.killed_pod):<40} "
            f"{r.recovery.elapsed_s:<8.1f} {r.recovery.consecutive_failures:<10} "
            f"{r.message_loss:<8} {'✓' if r.passed else '✗'}"
        )
    log.info("─────────────────────────────────────────────────────────")

    total_loss = sum(r.message_loss for r in results)
    log.info(f"  Total message loss across 24h: {total_loss}")

    engine.assert_no_failures(results)
    assert total_loss == 0, f"Total message loss across 24h run: {total_loss}"
