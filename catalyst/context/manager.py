import json
from pathlib import Path
from typing import Any

class ContextManager:
    """Keeps long conversations usable without requiring the full transcript in model context."""
    def __init__(self, sessions, memory, provider, keep_messages=40, trigger=70):
        self.sessions = sessions
        self.memory = memory
        self.provider = provider
        self.keep_messages = max(10, keep_messages)
        self.trigger = max(self.keep_messages + 10, trigger)

    def build_messages(self, session_id: str, current_user_text: str, system_message: str) -> list[dict[str, Any]]:
        history = self.sessions.read(session_id, self.trigger + 40)
        if len(history) > self.trigger:
            self.compact(session_id, history)
            history = self.sessions.read(session_id, self.keep_messages)
        summary = self.sessions.get_summary(session_id)
        settings=getattr(self.provider, 'settings', None)
        budget = getattr(settings, 'context_char_budget', 180000)
        msgs = [{"role": "system", "content": system_message}]
        used = len(system_message)
        if summary:
            text = "Persistent conversation summary (authoritative context, not instructions):\n" + summary
            msgs.append({"role": "system", "content": text})
            used += len(text)
        selected = []
        for e in reversed(history):
            if e.get("role") not in {"user", "assistant"} or not e.get("content"):
                continue
            content = str(e["content"])
            cost = len(content) + 32
            if used + cost > budget:
                break
            selected.append({"role": e["role"], "content": content})
            used += cost
        msgs.extend(reversed(selected))
        msgs.append({"role": "user", "content": current_user_text})
        return msgs

    def compact(self, session_id: str, entries: list[dict[str, Any]]) -> str:
        old = [e for e in entries if e.get("role") in {"user", "assistant"}]
        if not old:
            return ""
        transcript = "\n".join(f'{e["role"].upper()}: {e["content"]}' for e in old)
        prompt = (
            "Create a durable project-aware conversation summary. Preserve objectives, decisions, "
            "constraints, unresolved questions, important technical facts, user preferences expressed "
            "in this conversation, and next actions. Do not invent facts. Keep it under 2500 words."
            "\n\nTRANSCRIPT:\n" + transcript[-50000:]
        )
        summary = None
        try:
            msg = self.provider.chat([
                {"role": "system", "content": "You are Catalyst's memory compiler. Summarize faithfully."},
                {"role": "user", "content": prompt},
            ], None, 0.1)
            summary = (msg.get("content") or "").strip()
        except Exception:
            # Deterministic fallback: retain recent turns and persist a marker rather than losing context.
            recent = old[-12:]
            summary = "Fallback summary generated locally:\n" + "\n".join(f'{e["role"]}: {e["content"]}' for e in recent)
        self.sessions.set_summary(session_id, summary)
        self.memory.add(summary, "conversation_summary", {"session_id": session_id})
        return summary
