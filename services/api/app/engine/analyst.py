"""AI analyst: structured diff in -> strict JSON insight out.

Design rules (see docs/ARCHITECTURE.md § AI analyst contract):
  * The model only sees the supplied changes + watchlist context. It must not invent metrics.
  * Output is strict JSON; we parse tolerantly and degrade to a raw-text summary on failure.
  * One insight per cluster (competitor or keyword) so the feed reads like a brief, not a wall.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any

from ..config import get_settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are AdWatch's paid-search analyst. You write short, concrete briefs for a marketing team
about what their competitors just did in Google Ads and what changed in category demand.

Rules:
- Reason ONLY from the changes provided. Never invent numbers, spend, CTR, or intent you cannot see.
- Prefer 2-3 specific, testable actions over generic advice. Each action gets an effort (low/medium/high)
  and urgency (now / this_week / monitor).
- Plain English. No hype. No bullet characters inside strings. Do not name any third-party company
  other than the advertiser domains present in the data.
- Respond with a single JSON object and nothing else:
{
  "summary": "<2-4 sentences: what happened>",
  "why_it_matters": "<1-3 sentences: what it signals about competitor strategy or demand>",
  "recommended_actions": [
    {"action": "<imperative>", "rationale": "<why, tied to a change>", "effort": "low|medium|high", "urgency": "now|this_week|monitor"}
  ],
  "confidence": <0.0-1.0, how sure you are the signal is real given how many changes support it>
}"""


def _cluster(changes: list[dict[str, Any]]) -> dict[tuple[str, int], list[dict[str, Any]]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for c in changes:
        groups[(c["subject_type"], c["subject_id"])].append(c)
    return groups


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def build_user_prompt(context: dict[str, Any], changes: list[dict[str, Any]]) -> str:
    slim = [
        {
            "kind": c["kind"],
            "severity": c["severity"],
            "subject": f'{c["subject_type"]}:{c.get("subject_label", c["subject_id"])}',
            "payload": c.get("payload", {}),
        }
        for c in changes[:30]
    ]
    return (
        "WATCHLIST CONTEXT\n"
        + json.dumps(context, indent=1)
        + "\n\nCHANGES DETECTED SINCE LAST RUN\n"
        + json.dumps(slim, indent=1, default=str)
        + "\n\nWrite the brief as JSON."
    )


class Analyst:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        s = get_settings()
        self.api_key = api_key or s.anthropic_api_key
        self.model = model or s.anthropic_model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def analyze_cluster(self, context: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.api_key:
            return self._fallback(changes, reason="ANTHROPIC_API_KEY not set")
        prompt = build_user_prompt(context, changes)
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=900,
                temperature=0.2,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(getattr(b, "text", "") for b in msg.content)
        except Exception as e:  # network, auth, model-not-found
            log.exception("analyst call failed")
            return self._fallback(changes, reason=f"model error: {e}")
        parsed = _extract_json(text)
        if not parsed:
            return {"summary": text[:2000], "why_it_matters": "", "recommended_actions": [], "confidence": 0.0, "model": self.model}
        parsed.setdefault("recommended_actions", [])
        parsed.setdefault("why_it_matters", "")
        parsed["confidence"] = float(parsed.get("confidence") or 0.0)
        parsed["model"] = self.model
        return parsed

    def analyze(self, context: dict[str, Any], changes: list[dict[str, Any]]) -> list[tuple[list[int], dict[str, Any]]]:
        """Returns [(change_ids, insight_dict), ...] — one per subject cluster."""
        out: list[tuple[list[int], dict[str, Any]]] = []
        for _, group in _cluster(changes).items():
            ids = [c["id"] for c in group if "id" in c]
            out.append((ids, self.analyze_cluster(context, group)))
        return out

    @staticmethod
    def _fallback(changes: list[dict[str, Any]], *, reason: str) -> dict[str, Any]:
        """Deterministic, honest fallback so the demo never shows an empty card."""
        kinds = defaultdict(int)
        for c in changes:
            kinds[c["kind"]] += 1
        label = changes[0].get("subject_label", "") if changes else ""
        parts = [f"{n} × {k.replace('_', ' ')}" for k, n in sorted(kinds.items())]
        return {
            "summary": f"{label}: " + ", ".join(parts) + ".",
            "why_it_matters": "Automated summary (AI analyst unavailable: " + reason + ").",
            "recommended_actions": [
                {"action": "Review the listed changes manually", "rationale": "AI analysis was not available for this run", "effort": "low", "urgency": "this_week"}
            ],
            "confidence": 0.0,
            "model": "fallback",
        }
