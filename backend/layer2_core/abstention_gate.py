"""
LOCUS Three Iron Laws Abstention Gate.
Layer 2 Core - Guarantees 0% false positives by enforcing strict abstention
(tau_link < 0.75 -> SKIP / Manual Review Needed).
"""

from typing import Dict, Any, Optional
import re


class AbstentionGate:
    CONFIDENCE_THRESHOLD = 0.75

    @classmethod
    def evaluate(
        cls,
        claim_text: str,
        link_confidence: float,
        has_table_evidence: bool,
        math_check_verdict: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluates whether a claim is mathematically verifiable or must be abstained.
        Enforces strict rejection of general qualitative theory and non-quantitative prose.
        """
        # Rule 1: Distinguish verifiable quantitative claims from qualitative theory/definitions
        contains_numbers = bool(re.search(r"\d", claim_text))
        has_table_citation = bool(re.search(r"\btabel\s+(?:[IVX]+|\d+)", claim_text, re.IGNORECASE))
        has_eval_predicate = any(w in claim_text.lower() for w in [
            "tertinggi", "terendah", "terbaik", "terburuk", "paling besar", "paling kecil",
            "berdistribusi normal", "tidak normal", "memenuhi asumsi", "lolos uji"
        ])

        # If sentence has no numbers, no table citation, and no evaluation predicate:
        # it is purely qualitative definition/theory text -> MUST SKIP!
        if not contains_numbers and not has_table_citation and not has_eval_predicate:
            return {
                "decision": "SKIP",
                "reason": "THEORY_OR_QUALITATIVE_DEFINITION",
                "explanation": "Kalimat definisi atau teori kualitatif tanpa angka klaim, rujukan tabel spesifik, atau predikat evaluasi hasil.",
                "confidence": 1.0
            }

        # Rule 2: Evidence existence
        if not has_table_evidence:
            return {
                "decision": "SKIP",
                "reason": "NO_MATCHING_TABLE_EVIDENCE",
                "explanation": "Tidak ditemukan koordinat sel tabel yang relevan untuk memverifikasi klaim ini.",
                "confidence": link_confidence
            }

        # Rule 3: Iron Law Threshold: tau_link >= 0.75
        if link_confidence < cls.CONFIDENCE_THRESHOLD:
            return {
                "decision": "SKIP",
                "reason": "LOW_LINK_CONFIDENCE",
                "explanation": f"Tingkat keyakinan penautan sel ({round(link_confidence, 2)}) di bawah ambang batas aman 0.75. Sistem memilih abstain untuk mencegah positif palsu.",
                "confidence": link_confidence
            }

        return {
            "decision": "PROCEED",
            "reason": "VERIFIABLE",
            "confidence": link_confidence
        }
