from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
import re


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    confidence: float
    supported_claims: int
    unsupported_claims: int
    contradictions: int
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["reasons"] = list(self.reasons)
        return data


class ClaimVerifier:
    """Lightweight structural verifier for model/tool output.

    It never fabricates truth. It only marks a claim supported when supplied evidence
    shares meaningful terms or comes from an explicitly trusted deterministic event.
    """

    _SENTENCE = re.compile(r"(?<=[.!?])\s+")

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-zA-Z0-9_]{3,}", str(text).lower()))

    def verify(self, answer: str, evidence: Iterable[dict[str, Any]] | None = None) -> VerificationResult:
        claims = [x.strip() for x in self._SENTENCE.split(str(answer or "")) if len(x.strip()) >= 18]
        ev = list(evidence or [])
        supported = 0
        unsupported = 0
        contradictions = 0
        reasons: list[str] = []
        for claim in claims:
            ct = self._tokens(claim)
            best = 0.0
            negative = False
            trusted = False
            for item in ev:
                text = str(item.get("statement") or item.get("content") or item.get("result") or "")
                overlap = len(ct & self._tokens(text)) / max(1, len(ct))
                best = max(best, overlap)
                kind = str(item.get("kind") or item.get("event") or "").lower()
                if kind in {"verification", "test", "success", "deterministic", "source", "tool"} and overlap >= 0.18:
                    trusted = True
                if kind in {"failure", "contradiction", "negative", "error"} and overlap >= 0.18:
                    negative = True
            if negative:
                contradictions += 1
                reasons.append(f"contradicting evidence intersects claim: {claim[:160]}")
            elif trusted or best >= 0.34:
                supported += 1
            else:
                unsupported += 1
                reasons.append(f"no strong supporting evidence for claim: {claim[:160]}")
        total = max(1, supported + unsupported + contradictions)
        confidence = max(0.0, min(1.0, (supported - 0.5 * contradictions) / total))
        verified = bool(claims) and unsupported == 0 and contradictions == 0 and supported > 0
        if not claims:
            verified = False
            reasons.append("no sufficiently explicit claims were available for verification")
        return VerificationResult(verified, round(confidence, 3), supported, unsupported, contradictions, tuple(reasons[-12:]))
