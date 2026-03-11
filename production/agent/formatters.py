"""
production/agent/formatters.py
Channel-specific response formatting extracted from tools.py.

Rules sourced from:
  - context/brand-voice.md
  - specs/transition-checklist.md §5 (Response Patterns)
  - specs/customer-success-fte-spec.md §6.2 (NEVER block)
"""

import re
from typing import Optional

# ── Channel constraints ───────────────────────────────────────────────────────
# From brand-voice.md and discovery-log.md

CHANNEL_PARAMS: dict[str, dict] = {
    "email": {
        "max_chars": 3500,           # ~500 words
        "preferred_chars": None,
        "style": "formal",
        "markdown": True,
        "greeting_fmt": "Hi {name},",
        "sign_off": "\n\nBest regards,\nNimbusFlow Support\nTicket: {ticket_id}",
    },
    "whatsapp": {
        "max_chars": 1600,           # Twilio hard limit
        "preferred_chars": 300,      # Prefer ≤300 (D-004)
        "style": "conversational",
        "markdown": False,           # Plain text only (D-004)
        "greeting_fmt": None,        # Never greet on WhatsApp (D-004)
        "sign_off": "\nRef: {ticket_id}",
    },
    "web_form": {
        "max_chars": 2100,           # ~300 words
        "preferred_chars": None,
        "style": "semi-formal",
        "markdown": False,           # Rendered as plain text in UI
        "greeting_fmt": "Hi {name},",
        "sign_off": "\n\nHope that helps! — NimbusFlow Support\nTicket: {ticket_id}",
    },
}

# ── Filler phrases to strip ───────────────────────────────────────────────────
# From brand-voice.md §Language Rules and transition-checklist.md §5.4

_FILLER_OPENERS: list[str] = [
    "Great question!",
    "Great question.",
    "Absolutely!",
    "Absolutely.",
    "Certainly!",
    "Certainly.",
    "Of course!",
    "Of course.",
    "Sure thing!",
    "Sure thing.",
    "I would be happy to help!",
    "I would be happy to help.",
    "I'd be happy to help!",
    "I'd be happy to help.",
    "Thank you for reaching out!",
    "Thank you for reaching out.",
    "Thanks for reaching out!",
    "Thanks for reaching out.",
    "That's a great question!",
    "That's a great question.",
]

# ── Empathy openers ───────────────────────────────────────────────────────────
# From brand-voice.md §Empathy Phrases and transition-checklist.md §5

EMPATHY_OPENERS: dict[str, list[str]] = {
    "email": [
        "That sounds frustrating — let's sort this out.",
        "I can see why that's confusing. Here's what's happening:",
        "That shouldn't be happening. Let me look into this.",
        "Thanks for bearing with us on this. Here's the fix:",
    ],
    "whatsapp": [
        "That's frustrating — here's the fix:",
        "Got it. Let's sort this out:",
    ],
    "web_form": [
        "That sounds frustrating — let's sort this out.",
        "I can see why that's confusing. Here's what's happening:",
        "That shouldn't be happening. Let me look into this.",
    ],
}

# Sentiment thresholds per channel (from discovery-log.md §5.4)
EMPATHY_THRESHOLDS: dict[str, float] = {
    "email": 0.5,
    "whatsapp": 0.35,
    "web_form": 0.45,
}


def _strip_filler(text: str) -> str:
    """Remove known filler openers from the start of a response."""
    stripped = text.strip()
    for filler in _FILLER_OPENERS:
        if stripped.startswith(filler):
            stripped = stripped[len(filler):].lstrip(" \n")
    return stripped


def _strip_markdown_for_whatsapp(text: str) -> str:
    """
    Convert markdown to WhatsApp-safe plain text.
    WhatsApp uses *bold*, not **bold**; no headers; no links.
    """
    # **bold** → *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # __italic__ → _italic_
    text = re.sub(r"__(.+?)__", r"_\1_", text)
    # ### headers → plain text (just the text)
    text = re.sub(r"#{1,6}\s+", "", text)
    # [link text](url) → link text
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    # Markdown bullets (- item, * item) → plain bullets
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)
    # Remove code blocks (backticks)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text


def format_response(
    content: str,
    channel: str,
    customer_name: Optional[str] = None,
    ticket_id: str = "",
    sentiment_score: Optional[float] = None,
    is_escalation: bool = False,
) -> str:
    """
    Apply all channel-specific formatting rules to a raw response draft.

    Steps:
    1. Strip filler openers
    2. Optionally prepend empathy opener (based on sentiment threshold)
    3. Strip markdown if WhatsApp
    4. Add greeting (if applicable)
    5. Add sign-off with ticket reference
    6. Enforce max_chars limit

    Returns the fully formatted, send-ready string.
    """
    params = CHANNEL_PARAMS.get(channel, CHANNEL_PARAMS["web_form"])
    name = customer_name or "there"

    # 1. Strip fillers
    content = _strip_filler(content)

    # 2. Empathy opener (only if not already an escalation message)
    if not is_escalation and sentiment_score is not None:
        threshold = EMPATHY_THRESHOLDS.get(channel, 0.5)
        if sentiment_score < threshold:
            openers = EMPATHY_OPENERS.get(channel, EMPATHY_OPENERS["email"])
            # Pick opener deterministically based on score bucket
            idx = int(sentiment_score * 10) % len(openers)
            opener = openers[idx]
            if not content.startswith(opener):
                content = opener + "\n\n" + content

    # 3. Strip markdown for WhatsApp
    if not params["markdown"]:
        content = _strip_markdown_for_whatsapp(content)

    # 4. Assemble with greeting and sign-off
    sign_off = params["sign_off"].format(ticket_id=ticket_id or "")

    if params["greeting_fmt"] and channel != "whatsapp":
        greeting = params["greeting_fmt"].format(name=name)
        full = f"{greeting}\n\n{content.strip()}{sign_off}"
    else:
        # WhatsApp: no greeting, no closing formula
        full = f"{content.strip()}{sign_off}"

    # 5. Enforce length limit
    max_chars = params["max_chars"]
    if len(full) > max_chars:
        if channel == "whatsapp":
            note = "... [see next message]"
        else:
            note = "..."
        full = full[: max_chars - len(note)] + note

    # 6. Warn (log) if over preferred limit on WhatsApp
    preferred = params.get("preferred_chars")
    if preferred and len(full) > preferred:
        import logging
        logging.getLogger(__name__).warning(
            "WhatsApp response %d chars (preferred ≤%d)", len(full), preferred
        )

    return full


def char_count(text: str) -> int:
    return len(text)


def within_channel_limit(text: str, channel: str) -> bool:
    params = CHANNEL_PARAMS.get(channel, CHANNEL_PARAMS["web_form"])
    return len(text) <= params["max_chars"]
