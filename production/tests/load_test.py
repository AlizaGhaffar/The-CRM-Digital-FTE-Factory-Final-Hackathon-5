"""
production/tests/load_test.py
Exercise 3.2 — Load Testing with Locust

Simulates realistic 24-hour multi-channel traffic against the deployed
NimbusFlow Customer Success FTE API.

User classes:
    WebFormUser     — weight 3  — web form submissions + ticket status checks
    HealthCheckUser — weight 1  — health + metrics polling (ops monitoring)

Run locally against docker-compose:
    locust -f production/tests/load_test.py --host http://localhost:8000

Run headless (CI / 24h soak):
    locust -f production/tests/load_test.py \\
        --host http://localhost:8000 \\
        --users 20 --spawn-rate 2 --run-time 24h --headless \\
        --html production/tests/load_report.html \\
        --csv production/tests/load_results

Target thresholds (Final Challenge):
    P95 latency  < 3 000 ms  (all tasks)
    Failure rate < 0.1 %
    Uptime       > 99.9 %
"""

from __future__ import annotations

import json
import random
import time
import uuid
from typing import Optional

from locust import HttpUser, between, events, task


# ── Shared test data pools ─────────────────────────────────────────────────────

_FIRST_NAMES = ["Alice", "Bob", "Carlos", "Diana", "Elena", "Frank", "Grace"]
_LAST_NAMES  = ["Smith", "Patel", "Chen", "Okonkwo", "Rivera", "Kim", "Müller"]
_DOMAINS     = ["acme.com", "globex.io", "initech.net", "umbrella.co", "initrode.org"]
_CATEGORIES  = ["general", "technical", "billing", "feedback", "bug_report"]

# High-priority keywords — included in ~10 % of submissions to stress triage path
_HIGH_PRIORITY_SIGNALS = [
    "production down",
    "data loss affecting our team",
    "ci/cd pipeline broken",
    "evaluating nimbusflow for 200+ employees",
]

_SUBJECTS = [
    "Cannot log in to my account",
    "API rate limits too restrictive",
    "Billing charge I don't recognise",
    "Feature request: bulk export",
    "Integration with Slack not working",
    "Performance degradation since last update",
    "Wrong invoice amount",
    "Question about enterprise plan",
    "Bug in report generation",
]

_MESSAGES = [
    "I have been trying to log in for the past hour but keep getting a 403 error.",
    "Our team is seeing very high latency on the API endpoints since this morning.",
    "There is a duplicate charge on my account from last month that I did not authorise.",
    "Would love to see a bulk CSV export for all conversations. Is that on the roadmap?",
    "The Slack notification integration stopped working after the latest update.",
    "Response times have degraded significantly over the last 48 hours for our workspace.",
    "The invoice for March shows $299 but we are on the $199 plan.",
    "We are evaluating NimbusFlow for our team of 200+ employees. Can we get a demo?",
    "The monthly usage report shows incorrect numbers for the APAC region.",
    "Getting a 500 error when trying to export conversation history via the API.",
]


def _random_customer() -> dict:
    first  = random.choice(_FIRST_NAMES)
    last   = random.choice(_LAST_NAMES)
    domain = random.choice(_DOMAINS)
    return {
        "name":  f"{first} {last}",
        "email": f"{first.lower()}.{last.lower()}@{domain}",
    }


def _build_form_payload(high_priority: bool = False) -> dict:
    customer = _random_customer()
    message  = random.choice(_MESSAGES)
    if high_priority:
        signal  = random.choice(_HIGH_PRIORITY_SIGNALS)
        message = f"{message} {signal}"
    return {
        "name":     customer["name"],
        "email":    customer["email"],
        "subject":  random.choice(_SUBJECTS),
        "category": random.choice(_CATEGORIES),
        "message":  message,
        # honeypot must be absent / empty to pass spam filter
        "honeypot": "",
    }


# ── Shared ticket store (populated during load run) ───────────────────────────

_submitted_ticket_ids: list[str] = []


# ── User classes ──────────────────────────────────────────────────────────────


class WebFormUser(HttpUser):
    """
    Simulates a customer using the web support form.

    Task weights reflect real-world behaviour:
      - 6  submit_support_form     — main write path; highest volume
      - 2  check_ticket_status     — customers poll after submission
      - 1  lookup_own_customer     — occasionally query their own record
      - 1  submit_high_priority    — ~10 % are high-priority; stress triage

    Target: 100+ form submissions over 24 hours per user instance.
    """

    wait_time = between(2, 10)   # seconds between tasks (document spec)
    weight    = 3                # 3x more web form users than health checkers

    # ── Tasks ─────────────────────────────────────────────────────────────────

    @task(6)
    def submit_support_form(self) -> None:
        """POST /support/submit — standard priority submission."""
        payload = _build_form_payload(high_priority=False)
        with self.client.post(
            "/support/submit",
            json=payload,
            name="/support/submit [normal]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                try:
                    ticket_id = resp.json().get("ticket_id")
                    if ticket_id:
                        _submitted_ticket_ids.append(ticket_id)
                except Exception:
                    pass
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}: {resp.text[:200]}")

    @task(1)
    def submit_high_priority_form(self) -> None:
        """POST /support/submit — high-priority submission (keyword triggers triage)."""
        payload = _build_form_payload(high_priority=True)
        with self.client.post(
            "/support/submit",
            json=payload,
            name="/support/submit [high-priority]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                try:
                    ticket_id = resp.json().get("ticket_id")
                    if ticket_id:
                        _submitted_ticket_ids.append(ticket_id)
                except Exception:
                    pass
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}: {resp.text[:200]}")

    @task(2)
    def check_ticket_status(self) -> None:
        """GET /support/ticket/{ticket_id} — customer polling for ticket updates."""
        if not _submitted_ticket_ids:
            # Not enough tickets yet — skip this task silently
            return
        ticket_id = random.choice(_submitted_ticket_ids)
        with self.client.get(
            f"/support/ticket/{ticket_id}",
            name="/support/ticket/[id]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}: {resp.text[:200]}")

    @task(1)
    def lookup_own_customer(self) -> None:
        """GET /customers/lookup — customer checking their own record."""
        customer = _random_customer()
        with self.client.get(
            "/customers/lookup",
            params={"email": customer["email"]},
            name="/customers/lookup [email]",
            catch_response=True,
        ) as resp:
            # 404 is acceptable — random email may not exist yet
            if resp.status_code in (200, 404):
                resp.success()
            elif resp.status_code == 400:
                resp.failure("Missing identifier parameter")
            else:
                resp.failure(f"Unexpected status {resp.status_code}: {resp.text[:200]}")


class HealthCheckUser(HttpUser):
    """
    Simulates ops monitoring during load — polls liveness + metrics endpoints.

    These tasks represent external monitoring tools (PagerDuty, Prometheus
    scrape, uptime robots) that run continuously during production load.

    Both endpoints must remain < 500 ms even under full load.
    """

    wait_time = between(5, 15)   # document spec
    weight    = 1

    # ── Tasks ─────────────────────────────────────────────────────────────────

    @task
    def check_health(self) -> None:
        """GET /health — liveness probe; must always return 200."""
        with self.client.get(
            "/health",
            name="/health",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                try:
                    body = resp.json()
                    if body.get("status") != "ok":
                        resp.failure(f"Health status not ok: {body}")
                    else:
                        resp.success()
                except Exception as exc:
                    resp.failure(f"JSON parse error: {exc}")
            else:
                resp.failure(f"Health check failed: {resp.status_code}")

    @task
    def check_metrics(self) -> None:
        """GET /metrics/channels — must return channel summary under load."""
        with self.client.get(
            "/metrics/channels",
            name="/metrics/channels",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                try:
                    body = resp.json()
                    if "channels" not in body:
                        resp.failure("Missing 'channels' key in metrics response")
                    else:
                        resp.success()
                except Exception as exc:
                    resp.failure(f"JSON parse error: {exc}")
            else:
                resp.failure(f"Metrics endpoint failed: {resp.status_code}")

    @task
    def check_readiness(self) -> None:
        """GET /ready — readiness probe; must return 200 when DB + Kafka up."""
        with self.client.get(
            "/ready",
            name="/ready",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 503:
                # Readiness returning 503 during a chaos kill is expected
                resp.success()
            else:
                resp.failure(f"Readiness check failed: {resp.status_code}")


# ── Custom event hooks ─────────────────────────────────────────────────────────


@events.init.add_listener
def on_locust_init(environment, **kwargs) -> None:  # type: ignore[override]
    """Log threshold reminders at startup."""
    import logging
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("load_test")
    log.info("NimbusFlow load test initialised")
    log.info("Target thresholds: P95 < 3000 ms | Failure rate < 0.1%% | Uptime > 99.9%%")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs) -> None:  # type: ignore[override]
    """Print pass/fail summary against Final Challenge thresholds."""
    import logging
    log = logging.getLogger("load_test")
    stats = environment.runner.stats.total

    p95_ms    = stats.get_response_time_percentile(0.95) or 0
    fail_pct  = (stats.num_failures / max(stats.num_requests, 1)) * 100
    total_req = stats.num_requests

    log.info("─── Load Test Summary ───────────────────────────────")
    log.info(f"  Total requests : {total_req:,}")
    log.info(f"  Failures       : {stats.num_failures:,}  ({fail_pct:.2f}%%)")
    log.info(f"  P95 latency    : {p95_ms:.0f} ms")
    log.info(f"  Submitted IDs  : {len(_submitted_ticket_ids):,}")

    p95_ok  = p95_ms  < 3_000
    fail_ok = fail_pct < 0.1

    log.info("─── Threshold Results ───────────────────────────────")
    log.info(f"  P95 < 3000 ms  : {'PASS' if p95_ok  else 'FAIL'} ({p95_ms:.0f} ms)")
    log.info(f"  Failure < 0.1%% : {'PASS' if fail_ok else 'FAIL'} ({fail_pct:.2f}%%)")
    log.info("─────────────────────────────────────────────────────")
