"""
LOCUS Explain-First Revision Builder.
Layer 3 Export - Crafts pedagogical scaffolding and safe revision sentences
locked to deterministic mathematical ground truth.
"""

from typing import Dict, Any, List


class RevisionBuilder:
    @staticmethod
    def build_pedagogical_card(finding: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates an Explain-First pedagogical gate: user must engage with the
        mathematical reason before unlocking the safe revision sentence.
        """
        prompt = finding.get("pedagogical_prompt", {})
        math_trace = finding.get("math_and_logic_trace", {})

        return {
            "finding_id": finding.get("finding_id"),
            "verdict": finding.get("verdict"),
            "severity": finding.get("severity", "MEDIUM"),
            "question": prompt.get("question", "Mengapa klaim ini memerlukan penyesuaian?"),
            "options": prompt.get("options", []),
            "formula_proof": math_trace.get("formula_display", ""),
            "safe_revised_sentence": prompt.get("safe_revised_sentence", "")
        }
