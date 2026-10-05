import json
import os

import anthropic

JUDGEMENT_TOOL_NAME = "record_judgement"

JUDGEMENT_TOOL_SCHEMA = {
    "type": "object",
    "required": ["priority", "reason", "uncertainty", "evidence", "alert"],
    "properties": {
        "priority": {"type": "integer", "enum": [1, 2, 3, 4]},
        "reason": {"type": "string"},
        "uncertainty": {"type": ["string", "null"]},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["message_ref", "source_field", "segment_index", "quote", "field"],
                "properties": {
                    "message_ref": {"type": "string", "description": "the msg_N ref this quote comes from"},
                    "source_field": {
                        "type": "string",
                        "enum": ["body", "subject", "sender", "to", "cc", "sent_at", "attachment_name"],
                    },
                    "segment_index": {
                        "type": ["integer", "null"],
                        "description": "set when source_field is body; which segment the quote is from",
                    },
                    "quote": {"type": "string", "description": "verbatim substring of that source"},
                    "field": {
                        "type": "string",
                        "enum": ["priority", "who", "what", "why", "action", "deadline", "reason"],
                    },
                },
            },
        },
        "alert": {
            "type": ["object", "null"],
            "properties": {
                "who": {"type": "string"},
                "what": {"type": "string"},
                "why": {"type": "string"},
                "action": {"type": "string"},
                "deadline": {"type": ["string", "null"]},
            },
        },
    },
}

TOPIC_PROMPT = """You are analyzing an email thread for an executive triage system. Generate a short, one-line \
summary of the thread's topic. Be concise and specific (e.g., "Q4 fabric samples request", "Invoice payment dispute", \
"Board meeting scheduled"). Do not include who, what, why details - just the topic itself. Reply with only the \
one-liner topic, nothing else."""

SYSTEM_PROMPT = """You are the Judge component of an executive email triage system for Yarns & Colors Co., Ltd. \
The executive is Jacky. You receive one already-grouped thread (a business matter that may span several source \
messages) and return a single draft judgement.

Priority is about what Jacky must do with this matter. One thread receives one priority:
1 Immediate Attention - ONLY: regulatory/compliance stop-production orders, formal customer escalations with \
cancellation threats, or decisions affecting >$100k revenue at risk. Material harm, not routine decisions. Examples: \
EPA orders plant shutdown; customer threatens to cancel large order; supplier demands urgent payment or stops shipment.
2 Action / Decision Required Today - routine approvals, decisions, or replies with a same-day deadline. Examples: \
approve a purchase order before 5pm, decide whether to pay for expedited shipping, call back a colleague today.
3 Reference / Observation - useful context, status updates, requests with no urgency. Examples: sample received, \
shipment on track, supplier asking followup question.
4 Filter / No Executive Attention - sales blasts, mass mail, system notices

IMPORTANT: The word "urgent", a senior sender, or being on Cc does NOT by itself raise priority. Judge by facts, not tone.
- "URGENT: approve my expense report by 5pm" = P2 (routine decision with deadline), not P1
- "Urgent: customer needs samples" = P3 (routine request), not P1 unless customer is escalating
- "URGENT order cancellation" from customer = P1 (escalation with revenue risk)

Most emails are P3 Reference. Escalate to P2 only for time-sensitive decisions. Escalate to P1 only for genuine crises.

Threads may be in English, Chinese, Italian, or Japanese. Read them in their original language. Alert prose (who, \
what, why, action, deadline) is written in English; quotes in evidence are verbatim text in the original language.

Every important claim - the priority itself, and every alert field - must be backed by at least one evidence \
entry naming the exact message (by its msg_N ref), the source field, and a verbatim quote copied from that \
field or segment. Do not invent a quote; do not paraphrase into a quote. If the thread does not clearly support \
a fact, do not assert it - put it in "uncertainty" instead and leave the related alert field out of your answer \
or leave uncertainty non-null explaining the gap.

When a thread spans multiple messages, the FIRST message usually sets the context and decision point. Follow-up \
replies, questions, or clarifications do NOT negate the original deadline or decision - they are part of the \
business event but do not change that Jacky must act on the original timeline. Example: "Customer needs decision \
by 5pm" (msg_1) followed by clarifying questions (msg_2, msg_3) still requires a 5pm response, even if the \
clarifications are unresolved.

Only produce alert fields when priority is 1 or 2:
- P1 alerts: who needs to act, what must be done immediately, why it's a crisis, action steps, hard deadline
- P2 alerts: who owns the decision, what approval/reply is needed, why it matters, action steps, today's deadline
For P3 or P4, set alert to null - no alert prose needed.

For alerts: "why" must be either a quoted consequence, or a reasoned inference that still cites the quotes it draws on.
Do not invent consequences. Deadline should only be filled when the thread states a specific time; otherwise leave it null.
If you cannot find evidence for all alert fields (who, what, why, action, deadline), mark as needs_evidence and omit alert.

Judge the thread as of its own latest message's sent date, not as of today - a March thread is not urgent just \
because it is being reviewed later.

If the input includes a "past_corrections" array, these are human-approved corrections from previous threads in \
the same conversation. Use the semantic_summary from each past correction to inform similar classifications: they \
reveal what Jacky values and how to distinguish priority levels in practice.

Call record_judgement exactly once."""

def _client() -> anthropic.Client:
    api_key=os.getenv("ANTHROPIC_API_KEY")
    base_url=os.getenv("ANTHROPIC_BASE_URL")
    if not api_key or not base_url:
        raise RuntimeError("ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL must be set in .env")
    
    return anthropic.Client(api_key=api_key, base_url=base_url)

def generate_topic(packet: dict, model: str = os.getenv("ANTHROPIC_MODEL")) -> str:
    client = _client()
    response = client.messages.create(
        model=model,
        max_tokens=200,
        system=TOPIC_PROMPT,
        messages=[{"role": "user", "content": json.dumps(packet, ensure_ascii=False, indent=2)}],
    )
    topic = response.content[0].text.strip()
    return topic

def judge_thread(packet: dict, model: str = os.getenv("ANTHROPIC_MODEL")) -> dict:
    client = _client()
    # kimi-k3 always thinks, and a named tool_choice ("specified") is rejected
    # while thinking is on. "any" forces the single judgement tool without naming it.
    kimi = bool(model) and model.lower().startswith("kimi")
    minimax = bool(model) and model.lower().startswith("minimax")
    request = {
        "model": model,
        "max_tokens": 16000 if kimi else 2000,
        "system": SYSTEM_PROMPT,
        "tools": [{
            "name": JUDGEMENT_TOOL_NAME,
            "description": "Record the draft judgement for the thread",
            "input_schema": JUDGEMENT_TOOL_SCHEMA,
        }],
        "tool_choice": (
            {"type": "any"} if kimi else {"type": "tool", "name": JUDGEMENT_TOOL_NAME}
        ),
        "messages": [{"role": "user", "content": json.dumps(packet, ensure_ascii=False, indent=2)}],
    }
    # reasoning_split is Anthropic-specific; don't add it for MiniMax
    if not kimi and not minimax:
        request["extra_body"] = {"reasoning_split": True}
    response = client.messages.create(**request)
    tool_use =next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        raise RuntimeError("LLM Model did not return a tool_use block with the judgement.")
    return tool_use.input 
