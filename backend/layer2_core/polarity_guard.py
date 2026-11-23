"""
LOCUS Metric Polarity & Assumption Test Inversion Guard.
Layer 2 Core - Enforces Indonesian academic metric directionality
and prevents common assumption test logic inversion traps.
"""

import json
import os
import re
from typing import Dict, Any, Optional, List, Tuple


class PolarityGuard:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Default to data/indo_metric_polarity_v1.json relative to workspace or file
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, "data", "indo_metric_polarity_v1.json")

        self.config_path = config_path
        self.higher_is_better: List[str] = []
        self.lower_is_better: List[str] = []
        self.prerequisite_tests: List[Dict[str, Any]] = []
        self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.higher_is_better = [m.lower() for m in data.get("higher_is_better", [])]
                self.lower_is_better = [m.lower() for m in data.get("lower_is_better", [])]
                self.prerequisite_tests = data.get("prerequisite_tests", [])

    def get_metric_polarity(self, metric_name: str) -> Tuple[int, str]:
        """
        Returns (+1, 'HIGHER_IS_BETTER') or (-1, 'LOWER_IS_BETTER') or (0, 'UNKNOWN').
        """
        clean_name = metric_name.lower().strip()
        for m in self.higher_is_better:
            if m in clean_name or clean_name in m:
                return (+1, "HIGHER_IS_BETTER (+1)")
        for m in self.lower_is_better:
            if m in clean_name or clean_name in m:
                return (-1, "LOWER_IS_BETTER (-1)")
        return (0, "NEUTRAL_OR_UNKNOWN (0)")

    def check_prerequisite_inversion(self, text: str, header_or_test: str = "") -> Optional[Dict[str, Any]]:
        """
        Checks whether the claim contains an inverted prerequisite logic for
        Kolmogorov-Smirnov, Shapiro-Wilk, or Levene tests.
        Example error: 'Data berdistribusi normal karena nilai Sig. 0,012 < 0,05'
        """
        combined = f"{header_or_test} {text}".lower()

        # 1. Negation check: If the text explicitly states a non-normal or non-homogenous result
        # (e.g. 'tidak normal', 'tidak berdistribusi normal', 'menolak h0', 'h0 ditolak', etc.),
        # this is statistically ACCURATE when p < 0.05 (reject H0). Return None (VALID).
        negation_indicators = [
            "tidak normal",
            "tidak berdistribusi normal",
            "tidak berdistribusi secara normal",
            "belum normal",
            "gagal berdistribusi normal",
            "bukan normal",
            "tidak homogen",
            "tidak memenuhi asumsi",
            "menolak h0",
            "h0 ditolak",
            "hipotesis nol ditolak",
            "non-parametrik",
            "nonparametrik"
        ]
        if any(neg in combined for neg in negation_indicators):
            return None

        for test in self.prerequisite_tests:
            test_name = test["name"].lower()
            has_test = (
                test_name in combined
                or ("normalitas" in combined and test["type"] == "normality")
                or ("homogenitas" in combined and test["type"] == "homogeneity")
            )

            if has_test:
                # Check for normality or homogeneity conclusion
                if test["type"] == "normality":
                    normal_claim = any(w in combined for w in ["normal", "kenormalan"])
                else:
                    normal_claim = any(w in combined for w in ["homogen", "kehomogenan"])

                # Check if claiming normal/homogen based on p LESS than 0.05 (< 0.05)
                # Ensure it is NOT greater than (> 0.05)
                has_greater_than = bool(re.search(r"([>≥]|lebih\s+besar|di\s+atas)\s*(0[,.]05|0[,.]01)", combined))
                if has_greater_than:
                    # Stating p > 0.05 is mathematically sound for H0 retention!
                    continue

                less_than_pattern = bool(re.search(r"(\bsig\.?|\bp-?value|\bp|\bnilai)?\s*([<≤]|lebih\s+kecil|kurang\s+dari)\s*(0[,.]05|0[,.]01)", combined))

                if normal_claim and less_than_pattern:
                    return {
                        "verdict": "PREREQUISITE_LOGIC_INVERSION",
                        "severity": "CRITICAL",
                        "test_detected": test["name"],
                        "rule_violated": test["decision_rule"],
                        "explanation": test["inversion_warning"],
                        "formula_display": f"{test['name']}: Sig < 0.05 implies reject H0 (Data NOT {test['type'].title()}) != Text Claim (Normal)"
                    }
        return None

    def audit_superlative_claim(
        self,
        claim_text: str,
        metric_name: str,
        candidates: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Checks claims like 'Model X terbaik karena memiliki RMSE tertinggi 0.92'
        against candidates [{'label': 'XGBoost', 'val': 0.41}, {'label': 'Random Forest', 'val': 0.92}]
        """
        polarity, polarity_label = self.get_metric_polarity(metric_name)
        if polarity == 0 or not candidates:
            return None

        # Check superlative words in claim
        is_best_claim = any(w in claim_text.lower() for w in [
            "terbaik", "unggul", "optimal", "teroptimal", "paling optimal", "paling unggul",
            "kinerja terbaik", "kinerja optimal", "performa terbaik", "performa optimal"
        ])
        claims_highest = any(w in claim_text.lower() for w in [
            "tertinggi", "paling tinggi", "nilai terbesar", "terbesar", "maksimal", "paling besar"
        ])
        claims_lowest = any(w in claim_text.lower() for w in [
            "terendah", "paling rendah", "nilai terkecil", "terkecil", "minimal", "paling kecil"
        ])

        # Determine true best candidate mathematically
        if polarity == +1:
            best_cand = max(candidates, key=lambda c: c["val"])
        else:  # -1 (e.g. RMSE, loss, MAE, latency)
            best_cand = min(candidates, key=lambda c: c["val"])

        # Check for polarity contradiction in text
        # If lower is better (RMSE) and author claims best because value is highest/terbesar
        if polarity == -1 and claims_highest and is_best_claim:
            claimed_cand_label = None
            for c in candidates:
                if c["label"].lower() in claim_text.lower():
                    claimed_cand_label = c["label"]
                    break

            formula = (
                f"ArgBest({metric_name}, polarity=-1) = min({', '.join([f'{c.get('val')} ({c.get('label')})' for c in candidates])}) "
                f"= {best_cand.get('val')} ({best_cand.get('label')})"
            )

            return {
                "verdict": "POLARITY_INVERSION_ERROR",
                "severity": "HIGH",
                "metric_name": metric_name,
                "metric_polarity": polarity_label,
                "claimed_model": claimed_cand_label,
                "true_best_model": best_cand.get("label"),
                "true_best_val": best_cand.get("val"),
                "formula_display": formula,
                "explanation": (
                    f"Kesalahan Arah Metrik: {metric_name} adalah metrik galat (error), sehingga nilai yang lebih kecil (terendah) "
                    f"menunjukkan performa yang lebih baik. Model terbaik adalah {best_cand.get('label')} ({best_cand.get('val')}), "
                    f"bukan model dengan nilai tertinggi."
                )
            }

        return None
