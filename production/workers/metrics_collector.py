"""
production/workers/metrics_collector.py
Background worker that aggregates agent_metrics and generates
daily performance reports.

Runs on a schedule (every 60s for rolling metrics, daily for reports).
Reads from: agent_metrics, tickets, escalations, conversations
Writes to:  agent_metrics (aggregated rows), stdout/log

Run:
    python -m production.workers.metrics_collector

Performance targets (from specs/customer-success-fte-spec.md §5):
    - Escalation rate: < 20%
    - Resolution rate: > 80%
    - Avg agent latency: < 3000ms
    - Cross-channel identification: > 95%
"""

import asyncio
import logging
import os
import signal
from datetime import datetime, timezone

from production.database import queries

logger = logging.getLogger(__name__)

COLLECT_INTERVAL_S = int(os.getenv("METRICS_INTERVAL_S", "60"))
DAILY_REPORT_HOUR = int(os.getenv("METRICS_DAILY_REPORT_HOUR", "7"))  # 07:00 UTC

# Performance targets
TARGETS = {
    "escalation_rate_pct": 20.0,        # < 20%
    "resolution_rate_pct": 80.0,        # > 80%
    "avg_latency_ms": 3000.0,           # < 3 seconds
    "error_rate_pct": 0.1,              # < 0.1%
    "whatsapp_escalation_rate_pct": 10.0,
}


# ── Metric computation ────────────────────────────────────────────────────────

async def compute_rolling_metrics(window_minutes: int = 60) -> dict:
    """
    Compute rolling metrics over the last `window_minutes`.
    Returns a dict of metric_name → value.
    """
    pool = await queries.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                channel,
                COUNT(*)                                                  AS total,
                COUNT(*) FILTER (WHERE dimensions->>'escalated' = 'true') AS escalated,
                AVG((dimensions->>'latency_ms')::float)
                    FILTER (WHERE dimensions ? 'latency_ms')              AS avg_latency_ms,
                COUNT(*) FILTER (WHERE metric_name = 'processing_failure')AS failures
            FROM agent_metrics
            WHERE recorded_at >= NOW() - ($1 || ' minutes')::interval
              AND metric_name IN ('response_sent', 'processing_failure')
            GROUP BY channel
            """,
            str(window_minutes),
        )

    metrics: dict = {}
    total_all = 0
    escalated_all = 0

    for row in rows:
        ch = row["channel"] or "unknown"
        total = row["total"] or 0
        escalated = row["escalated"] or 0
        avg_lat = row["avg_latency_ms"]

        total_all += total
        escalated_all += escalated

        if total > 0:
            esc_rate = (escalated / total) * 100
            metrics[f"escalation_rate_pct.{ch}"] = round(esc_rate, 2)

        if avg_lat is not None:
            metrics[f"avg_latency_ms.{ch}"] = round(avg_lat, 0)

    if total_all > 0:
        metrics["escalation_rate_pct.overall"] = round(
            (escalated_all / total_all) * 100, 2
        )
        metrics["total_messages"] = total_all

    return metrics


async def compute_daily_summary() -> dict:
    """
    Compute full-day performance summary.
    Compares against production targets and flags violations.
    """
    pool = await queries.get_pool()
    async with pool.acquire() as conn:
        # Escalation rate by channel
        ticket_rows = await conn.fetch(
            """
            SELECT
                source_channel,
                COUNT(*)                                         AS total,
                COUNT(*) FILTER (WHERE status = 'escalated')    AS escalated,
                COUNT(*) FILTER (WHERE status = 'resolved')     AS resolved
            FROM tickets
            WHERE created_at >= CURRENT_DATE
            GROUP BY source_channel
            """
        )

        # Latency
        latency_rows = await conn.fetch(
            """
            SELECT
                channel,
                AVG(metric_value)   AS avg_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY metric_value) AS p95_ms,
                MAX(metric_value)   AS max_ms
            FROM agent_metrics
            WHERE metric_name = 'agent_latency_ms'
              AND recorded_at >= CURRENT_DATE
            GROUP BY channel
            """
        )

        # Sentiment trend
        sentiment_row = await conn.fetchrow(
            """
            SELECT
                AVG(sentiment_score)   AS avg_sentiment,
                COUNT(*) FILTER (WHERE sentiment_score < 0.3) AS negative_count,
                COUNT(*)               AS total_conversations
            FROM conversations
            WHERE created_at >= CURRENT_DATE
            """
        )

    summary: dict = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "channels": {},
        "latency": {},
        "sentiment": {},
        "violations": [],
    }

    total_all = 0
    escalated_all = 0

    for row in ticket_rows:
        ch = row["source_channel"]
        total = row["total"] or 0
        escalated = row["escalated"] or 0
        total_all += total
        escalated_all += escalated

        esc_rate = (escalated / total * 100) if total > 0 else 0
        res_rate = (row["resolved"] / total * 100) if total > 0 else 0

        summary["channels"][ch] = {
            "total_tickets": total,
            "escalated": escalated,
            "resolved": row["resolved"],
            "escalation_rate_pct": round(esc_rate, 2),
            "resolution_rate_pct": round(res_rate, 2),
        }

        # Flag violations
        target_esc = TARGETS.get(f"{ch}_escalation_rate_pct", TARGETS["escalation_rate_pct"])
        if esc_rate > target_esc:
            summary["violations"].append(
                f"escalation_rate.{ch}: {esc_rate:.1f}% > target {target_esc}%"
            )
        if res_rate < TARGETS["resolution_rate_pct"] and total > 5:
            summary["violations"].append(
                f"resolution_rate.{ch}: {res_rate:.1f}% < target {TARGETS['resolution_rate_pct']}%"
            )

    # Overall
    if total_all > 0:
        overall_esc = escalated_all / total_all * 100
        summary["overall_escalation_rate_pct"] = round(overall_esc, 2)
        if overall_esc > TARGETS["escalation_rate_pct"]:
            summary["violations"].append(
                f"escalation_rate.overall: {overall_esc:.1f}% > target 20%"
            )

    for row in latency_rows:
        ch = row["channel"]
        summary["latency"][ch] = {
            "avg_ms": round(row["avg_ms"] or 0, 0),
            "p95_ms": round(row["p95_ms"] or 0, 0),
            "max_ms": round(row["max_ms"] or 0, 0),
        }
        if (row["avg_ms"] or 0) > TARGETS["avg_latency_ms"]:
            summary["violations"].append(
                f"avg_latency.{ch}: {row['avg_ms']:.0f}ms > target 3000ms"
            )

    if sentiment_row:
        summary["sentiment"] = {
            "avg_score": round(sentiment_row["avg_sentiment"] or 0.5, 3),
            "negative_conversations": sentiment_row["negative_count"],
            "total_conversations": sentiment_row["total_conversations"],
        }

    return summary


# ── Worker loop ───────────────────────────────────────────────────────────────

class MetricsCollector:
    def __init__(self):
        self._running = False
        self._last_daily_report_date: str = ""

    async def start(self):
        self._running = True
        logger.info("Metrics collector started (interval=%ds)", COLLECT_INTERVAL_S)

    async def stop(self):
        self._running = False
        await queries.close_pool()
        logger.info("Metrics collector stopped")

    async def run(self):
        await self.start()
        try:
            while self._running:
                await self._collect_rolling()
                await self._maybe_daily_report()
                await asyncio.sleep(COLLECT_INTERVAL_S)
        except asyncio.CancelledError:
            logger.info("Metrics collector cancelled")
        finally:
            await self.stop()

    async def _collect_rolling(self):
        try:
            metrics = await compute_rolling_metrics(window_minutes=60)
            if metrics:
                logger.info("Rolling metrics (60m): %s", metrics)

                # Persist aggregated metric rows
                pool = await queries.get_pool()
                async with pool.acquire() as conn:
                    for name, value in metrics.items():
                        await conn.execute(
                            """
                            INSERT INTO agent_metrics
                                (metric_name, metric_value, dimensions)
                            VALUES ($1, $2, '{"aggregated": true}')
                            """,
                            f"rolling.{name}", float(value),
                        )
        except Exception as exc:
            logger.error("Rolling metrics collection failed: %s", exc, exc_info=True)

    async def _maybe_daily_report(self):
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        if now.hour == DAILY_REPORT_HOUR and self._last_daily_report_date != today:
            try:
                summary = await compute_daily_summary()
                self._last_daily_report_date = today

                violations = summary.get("violations", [])
                if violations:
                    logger.warning(
                        "DAILY REPORT — %d violations: %s",
                        len(violations), violations,
                    )
                else:
                    logger.info("DAILY REPORT — all targets met")

                logger.info("Daily summary: %s", summary)
            except Exception as exc:
                logger.error("Daily report failed: %s", exc, exc_info=True)


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    collector = MetricsCollector()
    loop = asyncio.get_running_loop()

    def _shutdown(sig):
        logger.info("Received %s, shutting down metrics collector...", sig.name)
        asyncio.create_task(collector.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    await collector.run()


if __name__ == "__main__":
    asyncio.run(main())
