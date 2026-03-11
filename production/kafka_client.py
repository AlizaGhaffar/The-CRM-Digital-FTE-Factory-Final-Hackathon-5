"""
production/kafka_client.py

NimbusFlow FTE — Kafka Client
Exercise 2.5: Centralised producer/consumer wrappers for all FTE topics.

Topics:
  fte.tickets.incoming          — new tickets from any channel
  fte.channels.email.inbound    — raw inbound email events
  fte.channels.whatsapp.inbound — raw inbound WhatsApp events
  fte.channels.webform.inbound  — raw inbound web-form submissions
  fte.channels.email.outbound   — outbound email payloads to send
  fte.channels.whatsapp.outbound— outbound WhatsApp payloads to send
  fte.escalations               — escalation events for human review
  fte.metrics                   — agent/system metrics snapshots
  fte.dlq                       — dead-letter queue for failed messages

Usage (producer):
    async with FTEKafkaProducer() as producer:
        await producer.send(TOPICS.TICKETS_INCOMING, {"ticket_id": "t-001", ...})

Usage (consumer):
    async with FTEKafkaConsumer(TOPICS.ESCALATIONS, group_id="escalation-worker") as consumer:
        await consumer.consume(my_handler)
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)

# ── Environment ────────────────────────────────────────────────────────────────

KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# ── Topic registry ─────────────────────────────────────────────────────────────


class TOPICS:
    """All FTE Kafka topic names — single source of truth."""

    TICKETS_INCOMING          = "fte.tickets.incoming"
    CHANNELS_EMAIL_INBOUND    = "fte.channels.email.inbound"
    CHANNELS_WHATSAPP_INBOUND = "fte.channels.whatsapp.inbound"
    CHANNELS_WEBFORM_INBOUND  = "fte.channels.webform.inbound"
    CHANNELS_EMAIL_OUTBOUND   = "fte.channels.email.outbound"
    CHANNELS_WHATSAPP_OUTBOUND= "fte.channels.whatsapp.outbound"
    ESCALATIONS               = "fte.escalations"
    METRICS                   = "fte.metrics"
    DLQ                       = "fte.dlq"

    # Convenience list — useful for admin/monitoring
    ALL: list[str] = [
        TICKETS_INCOMING,
        CHANNELS_EMAIL_INBOUND,
        CHANNELS_WHATSAPP_INBOUND,
        CHANNELS_WEBFORM_INBOUND,
        CHANNELS_EMAIL_OUTBOUND,
        CHANNELS_WHATSAPP_OUTBOUND,
        ESCALATIONS,
        METRICS,
        DLQ,
    ]


# ── Message envelope ───────────────────────────────────────────────────────────


@dataclass
class KafkaMessage:
    """Standard message envelope for all FTE topics."""

    type: str                                # e.g. "ticket.new", "escalation.created"
    payload: dict[str, Any]
    source: str = "fte-agent"               # originating service
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_bytes(self) -> bytes:
        return json.dumps(
            {
                "message_id": self.message_id,
                "type": self.type,
                "source": self.source,
                "ts": self.ts,
                "payload": self.payload,
            },
            default=str,
        ).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "KafkaMessage":
        raw = json.loads(data.decode("utf-8"))
        return cls(
            type=raw.get("type", "unknown"),
            payload=raw.get("payload", {}),
            source=raw.get("source", "unknown"),
            message_id=raw.get("message_id", str(uuid.uuid4())),
            ts=raw.get("ts", datetime.now(timezone.utc).isoformat()),
        )


# ── FTEKafkaProducer ──────────────────────────────────────────────────────────


class FTEKafkaProducer:
    """
    Async Kafka producer for all FTE topics.

    Features:
    - JSON serialisation with KafkaMessage envelope
    - gzip compression
    - Idempotent delivery (acks="all", enable_idempotence=True)
    - Automatic DLQ routing on send failure
    - Async context manager support
    """

    def __init__(
        self,
        bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
        *,
        enable_dlq: bool = True,
    ) -> None:
        self._bootstrap = bootstrap_servers
        self._enable_dlq = enable_dlq
        self._producer: Optional[AIOKafkaProducer] = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap,
            compression_type="gzip",
            acks="all",
            enable_idempotence=True,
            value_serializer=lambda v: v,   # we serialise manually
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
        await self._producer.start()
        logger.info("[kafka] producer started → %s", self._bootstrap)

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            self._producer = None
            logger.info("[kafka] producer stopped")

    async def __aenter__(self) -> "FTEKafkaProducer":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    async def send(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        event_type: str = "event",
        key: Optional[str] = None,
        source: str = "fte-agent",
    ) -> bool:
        """
        Publish a message to *topic*.

        Args:
            topic:      Target topic name (use TOPICS.* constants).
            payload:    Dict to include as the message payload.
            event_type: Human-readable event type string.
            key:        Optional partition key (e.g. ticket_id).
            source:     Originating service name.

        Returns:
            True on success, False if routed to DLQ.
        """
        if not self._producer:
            raise RuntimeError("Producer not started. Use `async with FTEKafkaProducer()` or call start().")

        msg = KafkaMessage(type=event_type, payload=payload, source=source)

        try:
            await self._producer.send_and_wait(
                topic,
                value=msg.to_bytes(),
                key=key,
            )
            logger.debug("[kafka] sent %s → %s (id=%s)", event_type, topic, msg.message_id)
            return True

        except KafkaError as exc:
            logger.error("[kafka] send failed topic=%s type=%s: %s", topic, event_type, exc)
            if self._enable_dlq and topic != TOPICS.DLQ:
                await self._send_to_dlq(topic, msg, str(exc))
            return False

    async def _send_to_dlq(self, original_topic: str, msg: KafkaMessage, error: str) -> None:
        """Route a failed message to the dead-letter queue."""
        dlq_payload = {
            "original_topic": original_topic,
            "original_message_id": msg.message_id,
            "original_type": msg.type,
            "original_payload": msg.payload,
            "error": error,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        dlq_msg = KafkaMessage(
            type="dlq.message",
            payload=dlq_payload,
            source=msg.source,
        )
        try:
            await self._producer.send_and_wait(TOPICS.DLQ, value=dlq_msg.to_bytes())
            logger.warning("[kafka] message routed to DLQ (original_topic=%s)", original_topic)
        except KafkaError as dlq_exc:
            logger.critical("[kafka] DLQ send also failed: %s", dlq_exc)

    # ── Convenience helpers ────────────────────────────────────────────────────

    async def send_ticket(self, ticket: dict[str, Any]) -> bool:
        return await self.send(
            TOPICS.TICKETS_INCOMING,
            ticket,
            event_type="ticket.new",
            key=ticket.get("ticket_id"),
        )

    async def send_escalation(self, escalation: dict[str, Any]) -> bool:
        return await self.send(
            TOPICS.ESCALATIONS,
            escalation,
            event_type="escalation.created",
            key=escalation.get("ticket_id"),
        )

    async def send_metrics(self, metrics: dict[str, Any]) -> bool:
        return await self.send(
            TOPICS.METRICS,
            metrics,
            event_type="metrics.snapshot",
        )

    async def send_outbound_email(self, email: dict[str, Any]) -> bool:
        return await self.send(
            TOPICS.CHANNELS_EMAIL_OUTBOUND,
            email,
            event_type="email.outbound",
            key=email.get("to"),
        )

    async def send_outbound_whatsapp(self, message: dict[str, Any]) -> bool:
        return await self.send(
            TOPICS.CHANNELS_WHATSAPP_OUTBOUND,
            message,
            event_type="whatsapp.outbound",
            key=message.get("to"),
        )


# ── FTEKafkaConsumer ──────────────────────────────────────────────────────────

# Handler signature: receives a KafkaMessage, returns None (or awaitable None)
MessageHandler = Callable[[KafkaMessage], Awaitable[None]]


class FTEKafkaConsumer:
    """
    Async Kafka consumer for a single FTE topic.

    Features:
    - Manual offset commit after successful handler execution
    - Auto-restart on transient errors
    - DLQ routing for handler exceptions (via injected producer)
    - Async context manager support

    Args:
        topic:               Topic to subscribe to (use TOPICS.* constants).
        group_id:            Consumer group ID.
        bootstrap_servers:   Kafka broker addresses.
        auto_offset_reset:   "earliest" or "latest".
        dlq_producer:        Optional FTEKafkaProducer for routing handler failures to DLQ.
    """

    def __init__(
        self,
        topic: str,
        *,
        group_id: str = "fte-default-group",
        bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset: str = "earliest",
        dlq_producer: Optional[FTEKafkaProducer] = None,
    ) -> None:
        self._topic = topic
        self._group_id = group_id
        self._bootstrap = bootstrap_servers
        self._auto_offset_reset = auto_offset_reset
        self._dlq_producer = dlq_producer
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._running = False

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap,
            group_id=self._group_id,
            auto_offset_reset=self._auto_offset_reset,
            enable_auto_commit=False,       # manual commit only
            value_deserializer=lambda v: v, # raw bytes; we parse in consume()
        )
        await self._consumer.start()
        self._running = True
        logger.info(
            "[kafka] consumer started topic=%s group=%s",
            self._topic, self._group_id,
        )

    async def stop(self) -> None:
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
            logger.info("[kafka] consumer stopped topic=%s", self._topic)

    async def __aenter__(self) -> "FTEKafkaConsumer":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    async def consume(self, handler: MessageHandler) -> None:
        """
        Poll messages indefinitely, calling *handler* for each one.

        Commits the offset only after a successful handler invocation.
        On handler exception, routes the message to DLQ (if producer provided)
        and commits anyway to avoid infinite retry loops.

        Call `stop()` to exit the loop gracefully.
        """
        if not self._consumer:
            raise RuntimeError("Consumer not started. Use `async with FTEKafkaConsumer()` or call start().")

        logger.info("[kafka] consuming from %s …", self._topic)

        async for record in self._consumer:
            if not self._running:
                break

            try:
                msg = KafkaMessage.from_bytes(record.value)
            except Exception as parse_exc:
                logger.error(
                    "[kafka] failed to parse message offset=%s: %s",
                    record.offset, parse_exc,
                )
                await self._consumer.commit()
                continue

            try:
                await handler(msg)
                await self._consumer.commit()
                logger.debug(
                    "[kafka] processed %s offset=%s id=%s",
                    msg.type, record.offset, msg.message_id,
                )
            except Exception as handler_exc:
                logger.error(
                    "[kafka] handler error topic=%s offset=%s id=%s: %s",
                    self._topic, record.offset, msg.message_id, handler_exc,
                )
                if self._dlq_producer:
                    await self._dlq_producer.send(
                        TOPICS.DLQ,
                        payload={
                            "original_topic": self._topic,
                            "original_message_id": msg.message_id,
                            "original_type": msg.type,
                            "original_payload": msg.payload,
                            "error": str(handler_exc),
                            "consumer_group": self._group_id,
                            "failed_at": datetime.now(timezone.utc).isoformat(),
                        },
                        event_type="dlq.handler_error",
                    )
                # Commit to advance past the failed message
                await self._consumer.commit()


# ── Multi-topic consumer helper ────────────────────────────────────────────────


class FTEKafkaMultiConsumer:
    """
    Subscribe to multiple topics with a single consumer instance.

    Useful for workers that need to fan-in several topics
    (e.g. an orchestrator that handles all inbound channel events).

    Args:
        topics:   List of topic names.
        handlers: Optional dict mapping topic → handler. Falls back to default_handler.
        default_handler: Called for any topic without a specific handler.
    """

    def __init__(
        self,
        topics: list[str],
        *,
        group_id: str = "fte-multi-group",
        bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset: str = "earliest",
        handlers: Optional[dict[str, MessageHandler]] = None,
        default_handler: Optional[MessageHandler] = None,
    ) -> None:
        self._topics = topics
        self._group_id = group_id
        self._bootstrap = bootstrap_servers
        self._auto_offset_reset = auto_offset_reset
        self._handlers = handlers or {}
        self._default_handler = default_handler
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._running = False

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            *self._topics,
            bootstrap_servers=self._bootstrap,
            group_id=self._group_id,
            auto_offset_reset=self._auto_offset_reset,
            enable_auto_commit=False,
        )
        await self._consumer.start()
        self._running = True
        logger.info("[kafka] multi-consumer started topics=%s group=%s", self._topics, self._group_id)

    async def stop(self) -> None:
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None

    async def __aenter__(self) -> "FTEKafkaMultiConsumer":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    async def consume(self) -> None:
        """Poll all subscribed topics and dispatch to the appropriate handler."""
        if not self._consumer:
            raise RuntimeError("Not started.")

        async for record in self._consumer:
            if not self._running:
                break
            try:
                msg = KafkaMessage.from_bytes(record.value)
                handler = self._handlers.get(record.topic, self._default_handler)
                if handler:
                    await handler(msg)
                else:
                    logger.warning("[kafka] no handler for topic=%s, skipping", record.topic)
                await self._consumer.commit()
            except Exception as exc:
                logger.error("[kafka] multi-consumer error topic=%s: %s", record.topic, exc)
                await self._consumer.commit()  # advance past bad message
