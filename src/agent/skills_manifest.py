"""
Agent Skills Manifest — NimbusFlow Customer Success FTE
Exercise 1.5: Define Agent Skills

Skills are reusable, composable capabilities the FTE agent invokes.
Each skill has a defined trigger, inputs, outputs, and test cases.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional
from enum import Enum


class SkillStatus(str, Enum):
    ACTIVE = "active"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"


@dataclass
class AgentSkill:
    """Definition of a single agent skill."""
    name: str
    description: str
    when_to_use: str
    inputs: dict[str, str]
    outputs: dict[str, str]
    constraints: list[str]
    test_cases: list[dict]
    status: SkillStatus = SkillStatus.ACTIVE
    version: str = "1.0"


# ── Skill 1: Knowledge Retrieval ────────────────────────────────────────────
KNOWLEDGE_RETRIEVAL_SKILL = AgentSkill(
    name="knowledge_retrieval",
    description="Search NimbusFlow product documentation to answer customer questions.",
    when_to_use=(
        "When a customer asks about product features, how to set up integrations, "
        "account settings, API usage, billing plan details, or any product-related question."
    ),
    inputs={
        "query": "str — the customer's question or topic",
        "max_results": "int — maximum number of docs to retrieve (default: 5)",
        "category": "Optional[str] — filter by doc category (e.g., 'billing', 'api')"
    },
    outputs={
        "results": "list[dict] — ranked list of relevant doc sections",
        "confidence": "float — relevance confidence (0.0–1.0)",
        "fallback_needed": "bool — True if no results found (triggers escalation)"
    },
    constraints=[
        "Only return information from product-docs.md",
        "Never fabricate features or functionality",
        "If confidence < 0.7 after 2 searches, set fallback_needed=True",
        "Max 5 results to avoid overwhelming agent context"
    ],
    test_cases=[
        {
            "input": "how do I reset my password",
            "expected_section": "Troubleshooting",
            "expected_confidence": "> 0.7"
        },
        {
            "input": "what are the API rate limits",
            "expected_section": "API & Webhooks",
            "expected_confidence": "> 0.8"
        },
        {
            "input": "xyznonexistentfeature123",
            "expected_fallback_needed": True
        }
    ]
)


# ── Skill 2: Sentiment Analysis ──────────────────────────────────────────────
SENTIMENT_ANALYSIS_SKILL = AgentSkill(
    name="sentiment_analysis",
    description="Analyze customer message sentiment to determine emotional state and appropriate response tone.",
    when_to_use=(
        "On EVERY incoming customer message before generating a response. "
        "Determines if empathy opener is needed and whether to escalate."
    ),
    inputs={
        "message": "str — the customer's full message text",
        "conversation_history": "Optional[list] — prior messages for context"
    },
    outputs={
        "score": "float — 0.0 (very negative) to 1.0 (very positive)",
        "level": "str — very_negative | negative | neutral | positive | very_positive",
        "escalation_recommended": "bool — True if score < 0.3",
        "empathy_opener_needed": "bool — True if score < 0.5"
    },
    constraints=[
        "Score < 0.1: immediately escalate, do not attempt resolution",
        "Score < 0.3: escalate after one resolution attempt",
        "Score < 0.5: prepend empathy opener to response",
        "Never share the score with the customer",
        "Consider ALL CAPS, multiple !!! as negative signals"
    ],
    test_cases=[
        {
            "input": "This is RIDICULOUS! Your product is BROKEN!",
            "expected_score": "< 0.3",
            "expected_level": "very_negative",
            "expected_escalation": True
        },
        {
            "input": "how do i reset password",
            "expected_score": "> 0.5",
            "expected_level": "neutral",
            "expected_escalation": False
        },
        {
            "input": "Love NimbusFlow! Quick question about dark mode",
            "expected_score": "> 0.7",
            "expected_level": "positive",
            "expected_escalation": False
        }
    ]
)


# ── Skill 3: Escalation Decision ──────────────────────────────────────────────
ESCALATION_DECISION_SKILL = AgentSkill(
    name="escalation_decision",
    description="Determine if a conversation should be escalated to human support and at what urgency.",
    when_to_use=(
        "After sentiment analysis and before/after knowledge retrieval. "
        "Also re-evaluate after each resolution attempt."
    ),
    inputs={
        "message": "str — customer message",
        "sentiment_score": "float — from sentiment_analysis skill",
        "resolution_attempts": "int — how many times we've tried to resolve",
        "customer_history": "dict — prior contact history",
        "channel": "str — email | whatsapp | web_form"
    },
    outputs={
        "should_escalate": "bool",
        "reason": "str — specific escalation reason code",
        "urgency": "str — critical | high | normal | low",
        "routing": "str — team to route to (billing, technical, security, legal, account)"
    },
    constraints=[
        "Legal keywords → critical escalation, no resolution attempt",
        "Security incidents → critical escalation to security@",
        "Data loss → critical escalation",
        "Chargeback threats → critical escalation to billing@",
        "Explicit human request → high urgency, no resolution attempt",
        "Repeat contact (3+) same issue → escalate regardless of sentiment",
        "Never attempt resolution after deciding to escalate"
    ],
    test_cases=[
        {
            "input": {"message": "I will sue you", "sentiment_score": 0.05},
            "expected": {"should_escalate": True, "urgency": "critical", "reason": "legal_threat"}
        },
        {
            "input": {"message": "can I speak to a human", "sentiment_score": 0.5},
            "expected": {"should_escalate": True, "urgency": "high", "reason": "explicit_human_request"}
        },
        {
            "input": {"message": "how do I export data", "sentiment_score": 0.7},
            "expected": {"should_escalate": False}
        }
    ]
)


# ── Skill 4: Channel Adaptation ──────────────────────────────────────────────
CHANNEL_ADAPTATION_SKILL = AgentSkill(
    name="channel_adaptation",
    description="Format agent responses appropriately for the target communication channel.",
    when_to_use=(
        "ALWAYS before sending any response via send_response tool. "
        "Never send raw unformatted text."
    ),
    inputs={
        "response_text": "str — the raw response content",
        "channel": "str — email | whatsapp | web_form",
        "customer_name": "Optional[str] — for personalized greeting",
        "ticket_id": "str — for reference inclusion",
        "is_escalation": "bool — use escalation language if True"
    },
    outputs={
        "formatted_response": "str — channel-appropriate final response",
        "char_count": "int — response length",
        "within_limit": "bool — True if within channel limits"
    },
    constraints=[
        "Email: max 2000 words, include greeting + signature",
        "WhatsApp: max 1600 chars, NO markdown, plain text only, max 2 messages",
        "Web Form: max 600 words, semi-formal",
        "WhatsApp: no 'Hi [Name]' opener — get straight to answer",
        "Email: always include ticket reference at bottom",
        "Never use filler openers: 'Great question!', 'Absolutely!', 'Certainly!'"
    ],
    test_cases=[
        {
            "input": {"channel": "whatsapp", "response_text": "A" * 2000},
            "expected": {"within_limit": False, "split_needed": True}
        },
        {
            "input": {"channel": "email", "customer_name": "Alice"},
            "expected_starts_with": "Hi Alice,"
        },
        {
            "input": {"channel": "whatsapp", "response_text": "Reset at nimbusflow.io/forgot-password"},
            "expected_no_markdown": True
        }
    ]
)


# ── Skill 5: Customer Identification ─────────────────────────────────────────
CUSTOMER_IDENTIFICATION_SKILL = AgentSkill(
    name="customer_identification",
    description="Identify and unify customer identity across all channels using available metadata.",
    when_to_use=(
        "On EVERY incoming message, before creating a ticket. "
        "Must resolve customer ID before any other action."
    ),
    inputs={
        "channel": "str — email | whatsapp | web_form",
        "email": "Optional[str] — from email or web form",
        "phone": "Optional[str] — from WhatsApp",
        "name": "Optional[str] — from form or email headers",
        "existing_identifiers_db": "dict — lookup table for cross-channel matching"
    },
    outputs={
        "customer_id": "str — unified UUID",
        "is_new_customer": "bool",
        "matched_channels": "list[str] — other channels this customer used",
        "customer_name": "str — best known name",
        "merged_history": "dict — unified history across all channels"
    },
    constraints=[
        "Email is primary identifier — always preferred",
        "Phone number maps to WhatsApp identifier",
        "Never merge customers without high-confidence match",
        "If cannot identify: ask for email to create customer record",
        "WhatsApp phone format: strip 'whatsapp:' prefix before storing"
    ],
    test_cases=[
        {
            "input": {"channel": "email", "email": "alex@company.com"},
            "expected": {"customer_id": "exists_or_created", "is_new_customer": "depends"}
        },
        {
            "input": {"channel": "whatsapp", "phone": "+14155559201"},
            "expected": {"customer_id": "resolved_or_new"}
        },
        {
            "input": {"channel": "web_form", "email": None, "phone": None},
            "expected": {"action": "ask_for_email"}
        }
    ]
)


# ── Skills Registry ──────────────────────────────────────────────────────────
SKILLS_MANIFEST: dict[str, AgentSkill] = {
    "knowledge_retrieval": KNOWLEDGE_RETRIEVAL_SKILL,
    "sentiment_analysis": SENTIMENT_ANALYSIS_SKILL,
    "escalation_decision": ESCALATION_DECISION_SKILL,
    "channel_adaptation": CHANNEL_ADAPTATION_SKILL,
    "customer_identification": CUSTOMER_IDENTIFICATION_SKILL,
}


def print_manifest_summary():
    """Print a human-readable summary of all skills."""
    print("\n" + "=" * 60)
    print("  NimbusFlow FTE — Agent Skills Manifest")
    print("=" * 60)
    for name, skill in SKILLS_MANIFEST.items():
        print(f"\n  [{skill.status.value.upper()}] {skill.name} v{skill.version}")
        print(f"  {skill.description[:80]}...")
        print(f"  Inputs:  {', '.join(skill.inputs.keys())}")
        print(f"  Outputs: {', '.join(skill.outputs.keys())}")
        print(f"  Tests:   {len(skill.test_cases)} test cases")


if __name__ == "__main__":
    print_manifest_summary()
