"""
production/workers/message_processor.py
Exercise 2.4 — Unified Message Processor

Kafka consumer that ingests messages from all channels and runs the
NimbusFlow Customer Success FTE agent.

Topics consumed:
    - nimbusflow.messages.email
    - nimbusflow.messages.whatsapp
    - nimbusflow.messages.web_form

Each message is a JSON payload with channel-specific fields.
Processed results are published to nimbusflow.responses.<channel>.

Run:
    python -m production.workers.message_processor
"""

import asyncio
import json
import logging
import os
import signal
import time
from datetime import datetime, timezone
from typing import Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from production.agent.customer_success_agent import run_agent as _run_agent
from production.database import queries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "fte-worker")
KAFKA_AUTO_OFFSET = "earliest"

INBOUND_TOPICS = [
    "nimbusflow.messages.email",
    "nimbusflow.messages.whatsapp",
    "nimbusflow.messages.web_form",
]

RESPONSE_TOPIC_PREFIX = "nimbusflow.responses"

MAX_RETRIES = int(os.getenv("WORKER_MAX_RETRIES", "3"))
RETRY_BACKOFF_S = float(os.getenv("WORKER_RETRY_BACKOFF", "2.0"))
SHUTDOWN_TIMEOUT_S = 10


# ── UnifiedMessageProcessor ───────────────────────────────────────────────────

class UnifiedMessageProcessor:
    """
    Process incoming messages from all channels through the FTE agent.

    Implements Exercise 2.4's eight-method pattern:
        start()                   — initialise Kafka + begin consuming
        process_message()         — main orchestration logic per message
        resolve_customer()        — find or create customer from email/phone
        get_or_create_conversation() — resume or open a new conversation
        store_message()           — persist inbound message to DB
        load_conversation_history()  — fetch prior turns for agent context
        run_agent()               — execute FTE with all 5 skills
        handle_error()            — graceful failure with dead-letter routing
    """

    def __init__(self):
        self._running = False
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._producer: Optional[AIOKafkaProducer] = None

    # ── 1. start ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialise Kafka producer + consumer and begin consuming messages."""
        logger.info("Starting UnifiedMessageProcessor, topics=%s", INBOUND_TOPICS)

        self._producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=None,      # Pre-serialised bytes
            compression_type="gzip",
            acks="all",
            enable_idempotence=True,
        )
        await self._producer.start()

        self._consumer = AIOKafkaConsumer(
            *INBOUND_TOPICS,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=KAFKA_GROUP_ID,
            auto_offset_reset=KAFKA_AUTO_OFFSET,
            enable_auto_commit=False,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            max_poll_records=10,
            session_timeout_ms=30_000,
            heartbeat_interval_ms=10_000,
        )
        await self._consumer.start()

        self._running = True
        logger.info("UnifiedMessageProcessor ready — waiting for messages")

        try:
            async for msg in self._consumer:
                if not self._running:
                    break

                payload = msg.value
                if not isinstance(payload, dict):
                    logger.warning("Non-dict payload on %s, skipping", msg.topic)
                    await self._consumer.commit()
                    continue

                # Ensure channel field is present (derive from topic if missing)
                if "channel" not in payload:
                    payload["channel"] = msg.topic.rsplit(".", 1)[-1]

                await self._consume_with_retry(payload)

                # Commit only after successful processing
                await self._consumer.commit()

        except asyncio.CancelledError:
            logger.info("Worker cancelled")
        except KafkaConnectionError as exc:
            logger.critical("Kafka connection lost: %s", exc, exc_info=True)
            raise
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Graceful shutdown: drain Kafka clients and close the DB pool."""
        self._running = False
        if self._consumer:
            await self._consumer.stop()
        if self._producer:
            await self._producer.stop()
        await queries.close_pool()
        logger.info("UnifiedMessageProcessor stopped")

    # ── 2. process_message ───────────────────────────────────────────────────

    async def process_message(self, payload: dict) -> None:
        """
        Main orchestration logic for a single inbound message.

        Flow (exactly as Exercise 2.4 document):
          1. Extract channel + customer identifiers from payload
          2. resolve_customer()        → unified customer_id
          3. get_or_create_conversation() → conversation_id
          4. store_message()           → persist inbound turn
          5. load_conversation_history() → prior turns for context
          6. run_agent()               → execute FTE with all 5 skills
          7. Publish response to nimbusflow.responses.<channel>
        """
        start_time = datetime.now(timezone.utc)

        channel = payload.get("channel", "web_form")
        channel_message_id = payload.get("message_id")
        customer_email = payload.get("from_email")
        customer_phone = payload.get("from_phone")
        customer_name = payload.get("from_name")
        body = payload.get("body", "")
        subject = payload.get("subject")
        thread_id = payload.get("thread_id") or payload.get("session_id")

        if not body.strip():
            logger.warning("Empty message body on channel=%s — skipping", channel)
            return

        # Step 2 — Resolve customer
        customer_id = await self.resolve_customer(
            email=customer_email,
            phone=customer_phone,
            name=customer_name,
            channel=channel,
        )

        # Step 3 — Get or create conversation
        conversation_id = await self.get_or_create_conversation(
            customer_id=customer_id,
            channel=channel,
        )

        # Step 4 — Store inbound message
        await self.store_message(
            conversation_id=conversation_id,
            channel=channel,
            direction="inbound",
            role="customer",
            content=body,
            channel_message_id=channel_message_id,
            thread_id=thread_id,
        )

        # Step 5 — Load prior conversation turns
        history = await self.load_conversation_history(conversation_id)

        # Step 6 — Run agent with all 5 skills
        result = await self.run_agent(
            message=body,
            channel=channel,
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_name=customer_name,
            conversation_id=conversation_id,
        )

        latency_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

        # Step 7 — Publish response for channel dispatcher
        response_topic = f"{RESPONSE_TOPIC_PREFIX}.{channel}"
        response_payload = {
            "ticket_id": result["ticket_id"],
            "customer_id": result["customer_id"],
            "conversation_id": result["conversation_id"],
            "channel": channel,
            "channel_message_id": channel_message_id,
            "response": result["response"],
            "escalated": result["escalated"],
            "escalation_id": result["escalation_id"],
            "sentiment_score": result["sentiment_score"],
            "latency_ms": latency_ms,
            # Routing hints for channel dispatchers
            "customer_email": customer_email,
            "customer_phone": customer_phone,
            "thread_id": thread_id,
            "subject": subject,
        }

        await self._producer.send_and_wait(
            response_topic,
            json.dumps(response_payload).encode(),
            key=(customer_email or customer_phone or "").encode(),
        )

        logger.info(
            "Processed %s message in %dms | ticket=%s | escalated=%s",
            channel,
            latency_ms,
            result["ticket_id"],
            result["escalated"],
        )

    # ── 3. resolve_customer ──────────────────────────────────────────────────

    async def resolve_customer(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        channel: str = "web_form",
    ) -> str:
        """
        Find existing customer by email or phone, or create a new one.

        Email is the primary key for email/web_form channels.
        Phone is the primary key for WhatsApp channel.
        Returns unified customer_id (UUID string).
        """
        customer_id = await queries.find_or_create_customer(
            email=email,
            phone=phone,
            name=name,
            channel=channel,
        )
        logger.debug(
            "resolve_customer: channel=%s email=%s phone=%s → %s",
            channel, email, phone, customer_id,
        )
        return customer_id

    # ── 4. get_or_create_conversation ────────────────────────────────────────

    async def get_or_create_conversation(
        self,
        customer_id: str,
        channel: str,
    ) -> str:
        """
        Resume the customer's active conversation (within 24 h) or open a
        new one. Returns conversation_id (UUID string).
        """
        conversation_id = await queries.get_or_create_conversation(
            customer_id=customer_id,
            channel=channel,
        )
        logger.debug(
            "get_or_create_conversation: customer=%s channel=%s → %s",
            customer_id, channel, conversation_id,
        )
        return conversation_id

    # ── 5. store_message ─────────────────────────────────────────────────────

    async def store_message(
        self,
        conversation_id: str,
        channel: str,
        direction: str,
        role: str,
        content: str,
        channel_message_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
        tool_calls: Optional[list] = None,
        sentiment_score: Optional[float] = None,
        delivery_status: str = "delivered",
    ) -> str:
        """Persist a single message turn to the database."""
        msg_id = await queries.store_message(
            conversation_id=conversation_id,
            channel=channel,
            direction=direction,
            role=role,
            content=content,
            channel_message_id=channel_message_id,
            thread_id=thread_id,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
            sentiment_score=sentiment_score,
            delivery_status=delivery_status,
        )
        return msg_id

    # ── 6. load_conversation_history ─────────────────────────────────────────

    async def load_conversation_history(self, conversation_id: str) -> list[dict]:
        """
        Fetch all prior messages for the conversation as [{role, content}, ...]
        ordered oldest-first, ready to be injected as agent context.
        """
        history = await queries.load_conversation_history(conversation_id)
        logger.debug(
            "load_conversation_history: conversation=%s turns=%d",
            conversation_id, len(history),
        )
        return history

    # ── 7. run_agent ─────────────────────────────────────────────────────────

    async def run_agent(
        self,
        message: str,
        channel: str,
        customer_email: Optional[str] = None,
        customer_phone: Optional[str] = None,
        customer_name: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> dict:
        """
        Execute the NimbusFlow Customer Success FTE with all 5 skills:

            1. create_ticket          — log the interaction
            2. get_customer_history   — detect repeat contacts
            3. analyze_sentiment      — gauge emotional state
            4. search_knowledge_base  — retrieve product documentation
            5. send_response          — deliver channel-appropriate reply

        Returns the agent result dict (ticket_id, response, escalated, …).
        """
        result = await _run_agent(
            message=message,
            channel=channel,
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_name=customer_name,
            conversation_id=conversation_id,
        )

        logger.debug(
            "run_agent: channel=%s tools=%s escalated=%s",
            channel, result.get("tool_calls"), result.get("escalated"),
        )
        return result

    # ── 8. handle_error ──────────────────────────────────────────────────────

    async def handle_error(self, payload: dict, exc: Exception) -> None:
        """
        Graceful failure handler.

        Behaviour:
        - Log the error with full context.
        - Record a processing_failure metric so dashboards surface it.
        - The caller's retry loop handles re-attempts; this method only
          handles the final dead-letter step.
        """
        channel = payload.get("channel", "unknown")
        logger.error(
            "handle_error: channel=%s error=%s payload_preview=%s",
            channel, exc, str(payload)[:200],
            exc_info=True,
        )
        try:
            await queries.record_metric(
                metric_name="processing_failure",
                metric_value=1.0,
                channel=channel,
                dimensions={
                    "error": str(exc)[:200],
                    "payload_preview": str(payload)[:200],
                },
            )
        except Exception as metric_exc:
            logger.warning("Could not record failure metric: %s", metric_exc)

    # ── Internal: retry wrapper ───────────────────────────────────────────────

    async def _consume_with_retry(self, payload: dict) -> None:
        """Retry process_message up to MAX_RETRIES with exponential backoff."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await self.process_message(payload)
                return
            except Exception as exc:
                logger.error(
                    "Processing error (attempt %d/%d): %s",
                    attempt, MAX_RETRIES, exc,
                    exc_info=True,
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_BACKOFF_S * attempt)
                else:
                    logger.critical(
                        "Message processing failed after %d attempts — dead-lettering",
                        MAX_RETRIES,
                    )
                    await self.handle_error(payload, exc)


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    processor = UnifiedMessageProcessor()

    loop = asyncio.get_running_loop()

    def _shutdown(sig):
        logger.info("Received signal %s, shutting down…", sig.name)
        asyncio.create_task(processor.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    await processor.start()


if __name__ == "__main__":
    asyncio.run(main())
