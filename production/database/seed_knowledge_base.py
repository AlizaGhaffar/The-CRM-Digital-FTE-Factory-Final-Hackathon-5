"""
production/database/seed_knowledge_base.py
Loads context/product-docs.md into knowledge_base table.
Chunks the document by section, generates OpenAI embeddings,
and upserts into PostgreSQL with pgvector.

Run once after schema migration:
    python production/database/seed_knowledge_base.py
"""

import asyncio
import os
import re
import hashlib
import logging
import httpx
from dotenv import load_dotenv
import asyncpg

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOCS_PATH = os.path.join(os.path.dirname(__file__), "../../context/product-docs.md")
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
BATCH_SIZE = 5  # Gemini embedding API: embed N chunks per call


def chunk_markdown(content: str) -> list[dict]:
    """
    Split markdown document into sections.
    Strategy: split on ## headings (level 2), keep h3+ nested.
    """
    chunks = []
    sections = re.split(r"\n(?=## )", content)

    for idx, section in enumerate(sections):
        if not section.strip():
            continue

        lines = section.strip().split("\n")
        title_line = lines[0].strip("# ").strip()
        body = "\n".join(lines[1:]).strip()

        if not body:
            continue

        # Determine category from title
        title_lower = title_line.lower()
        if any(w in title_lower for w in ["billing", "plan", "payment", "seat"]):
            category = "billing"
        elif any(w in title_lower for w in ["api", "webhook", "developer"]):
            category = "api"
        elif any(w in title_lower for w in ["sso", "security", "2fa", "auth"]):
            category = "security"
        elif any(w in title_lower for w in ["integration", "slack", "github", "figma"]):
            category = "integrations"
        elif any(w in title_lower for w in ["mobile", "app", "ios", "android"]):
            category = "mobile"
        elif any(w in title_lower for w in ["troubleshoot", "error", "fix", "issue"]):
            category = "troubleshooting"
        elif any(w in title_lower for w in ["getting started", "setup", "create"]):
            category = "getting_started"
        elif any(w in title_lower for w in ["export", "data", "gdpr"]):
            category = "data"
        else:
            category = "general"

        # Generate tags from title words
        stop_words = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "with"}
        tags = [
            w.lower().strip("()[]") for w in title_line.split()
            if len(w) > 3 and w.lower() not in stop_words
        ]

        chunks.append({
            "title": title_line,
            "content": body[:3000],  # Truncate very long sections
            "category": category,
            "tags": tags[:10],
            "source_doc": "product-docs.md",
            "chunk_index": idx,
            "content_hash": hashlib.sha256(body.encode()).hexdigest(),
        })

    return chunks


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Embed texts using Gemini native REST API (embedContent)."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    embeddings = []
    async with httpx.AsyncClient(timeout=60) as client:
        for text in texts:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBEDDING_MODEL}:embedContent?key={api_key}"
            resp = await client.post(url, json={
                "model": f"models/{EMBEDDING_MODEL}",
                "content": {"parts": [{"text": text}]},
            })
            resp.raise_for_status()
            embeddings.append(resp.json()["embedding"]["values"])
    return embeddings


async def seed():
    # Load and chunk docs
    if not os.path.exists(DOCS_PATH):
        logger.error(f"product-docs.md not found at {DOCS_PATH}")
        return

    with open(DOCS_PATH, "r") as f:
        content = f.read()

    chunks = chunk_markdown(content)
    logger.info(f"Chunked product-docs.md into {len(chunks)} sections")

    # Connect to DB
    pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DB", "fte_db"),
        user=os.getenv("POSTGRES_USER", "fte_user"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme"),
    )

    # Process in batches
    inserted = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [f"{c['title']}\n\n{c['content']}" for c in batch]

        logger.info(f"Embedding batch {i // BATCH_SIZE + 1} ({len(batch)} chunks)...")
        embeddings = await generate_embeddings(texts)

        async with pool.acquire() as conn:
            for chunk, embedding in zip(batch, embeddings):
                await conn.execute(
                    """
                    INSERT INTO knowledge_base
                        (title, content, content_hash, embedding,
                         category, source_doc, chunk_index, tags)
                    VALUES ($1, $2, $3, $4::vector, $5, $6, $7, $8)
                    ON CONFLICT DO NOTHING
                    """,
                    chunk["title"],
                    chunk["content"],
                    chunk["content_hash"],
                    str(embedding),
                    chunk["category"],
                    chunk["source_doc"],
                    chunk["chunk_index"],
                    chunk["tags"],
                )
                inserted += 1

    await pool.close()
    logger.info(f"Seeded {inserted} knowledge base entries successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
