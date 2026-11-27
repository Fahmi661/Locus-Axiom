"""
LOCUS Dual-Locale Column-Level Number Normalizer.
Layer 1 Perception - Resolves Indonesian PUEBI ('12,45' / '1.250') vs SPSS ('12.45' / '.000').
"""

import re
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any


STAT_DECIMAL_CONTEXT_KEYWORDS = (
    "sig", "p-value", "p value", "prob", "correl", "korelasi", "pearson",
    "spearman", "kendall", "cronbach", "alpha", "reliab", "beta",
    "r square", "r-square", "r2", "tolerance", "vif", "asymp", "exact",
    "std", "error", "deviation", "mean", "rata", "skew", "kurt",
    "coefficient", "koefisien", "unstandardized", "standardized"
)

STAT_DECIMAL_EXACT_TOKENS = {"r", "b", "t", "f", "z", "p", "se", "sd"}


class NumberNormalizer:
    @staticmethod
    def _has_stat_decimal_context(
        header_context: Optional[str] = None,
        table_context: Optional[str] = None,
    ) -> bool:
        ctx = f"{header_context or ''} {table_context or ''}".lower().strip()
        if not ctx:
            return False
        if any(kw in ctx for kw in STAT_DECIMAL_CONTEXT_KEYWORDS):
            return True
        tokens = set(re.findall(r"[a-z0-9]+", ctx))
        return bool(tokens & STAT_DECIMAL_EXACT_TOKENS)

    @staticmethod
    def clean_token(val_str: str) -> str:
        """Strips significance asterisks, parentheses, and normalizes Unicode minus signs."""
        if not val_str:
            return ""
        s = val_str.strip()
        # Normalize Unicode minus / dashes to ASCII hyphen-minus
        s = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d]", "-", s)
        # Remove markdown or asterisks like ***, **, *
        s = re.sub(r"[\*†‡]", "", s)
        # Remove wrapping parentheses if present
        s = re.sub(r"^\((.*?)\)$", r"\1", s)
        return s.strip()

    @classmethod
    def detect_column_locale(cls, column_values: List[str]) -> str:
        """
        Detects whether a column follows 'ID_PUEBI' (Indonesian PUEBI: comma decimal)
        or 'SPSS_US' (period decimal, leading dot like .000).
        """
        comma_decimal_votes = 0
        dot_decimal_votes = 0

        for raw in column_values:
            val = cls.clean_token(raw)
            if not val:
                continue

            # SPSS leading dot: e.g. .000, .452, -.318
            if re.match(r"^[+-]?\.\d+", val):
                dot_decimal_votes += 3
                continue

            # Zero-leading dot decimal: e.g. 0.000, -0.318 (never a PUEBI thousand separator)
            if re.match(r"^[+-]?0\.\d+$", val):
                dot_decimal_votes += 3
                continue

            # Standard Indonesian comma: e.g. 12,45 or 0,02
            if re.search(r"\d+,\d{1,5}$", val):
                if "." in val:
                    # Form like 1.250,50 -> definite Indonesian
                    comma_decimal_votes += 4
                else:
                    comma_decimal_votes += 2

            # Standard US dot: e.g. 12.45 or 0.02
            if re.search(r"\d+\.\d{1,5}$", val):
                if "," in val:
                    # Form like 1,250.50 -> US
                    dot_decimal_votes += 4
                else:
                    dot_decimal_votes += 2

        if dot_decimal_votes > comma_decimal_votes:
            return "SPSS_US"
        elif comma_decimal_votes > dot_decimal_votes:
            return "ID_PUEBI"
        return "UNKNOWN"

    @classmethod
    def parse_numeric(
        cls,
        raw_val: str,
        column_locale: Optional[str] = None,
        header_context: Optional[str] = None,
        table_context: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Parses a raw cell string into numeric metadata.
        Handles leading-dot SPSS decimals (.000, .042, -.318) and context-aware
        disambiguation so 3-decimal statistical values like 1.000 / 0.000 in
        correlation/reliability/sig tables are parsed as decimal floats rather
        than PUEBI thousand separators (1000).
        """
        cleaned = cls.clean_token(raw_val)
        if not cleaned:
            return None

        # Normalize SPSS leading dot/comma decimals: .000 -> 0.000, -.318 -> -0.318, ,17 -> 0.17
        leading_dot_matched = False
        if re.match(r"^[+-]?\s*\.\d+$", cleaned):
            cleaned = re.sub(r"^([+-]?)\s*\.(\d+)$", r"\g<1>0.\g<2>", cleaned)
            leading_dot_matched = True
        elif re.match(r"^[+-]?\s*,\d+$", cleaned):
            cleaned = re.sub(r"^([+-]?)\s*,(\d+)$", r"\g<1>0.\g<2>", cleaned)
            leading_dot_matched = True

        # Zero-leading decimal like 0.000 or -0.412 can NEVER be an Indonesian thousand separator
        is_zero_leading_dot = bool(re.match(r"^[+-]?0\.\d+$", cleaned))

        # 3-decimal statistical float like 1.000 / -1.000 / 0.852 inside stat/correlation/reliability/sig context
        is_stat_3dec_dot = (
            bool(re.match(r"^[+-]?\d\.\d{3}$", cleaned))
            and "," not in cleaned
            and cls._has_stat_decimal_context(header_context, table_context)
        )

        locale = column_locale
        if leading_dot_matched or is_zero_leading_dot or is_stat_3dec_dot:
            locale = "SPSS_US"
        elif not locale or locale == "UNKNOWN":
            # Heuristic single-token detection
            if "," in cleaned and "." in cleaned:
                # 1.250,50 -> ID; 1,250.50 -> US
                last_comma = cleaned.rfind(",")
                last_dot = cleaned.rfind(".")
                locale = "ID_PUEBI" if last_comma > last_dot else "SPSS_US"
            elif "," in cleaned:
                locale = "ID_PUEBI"
            else:
                locale = "SPSS_US"

        # Standardize representation to US float string for Decimal
        norm_str = cleaned
        if locale == "ID_PUEBI":
            # Remove thousands period, replace comma with dot
            norm_str = norm_str.replace(".", "").replace(",", ".")
        else:
            # Remove thousands comma
            norm_str = norm_str.replace(",", "")

        try:
            # Extract pure number part if token has prefixes like 't = 2.45' or 'p < 0.05'
            match = re.search(r"[+-]?\d+(?:\.\d+)?", norm_str)
            if not match:
                return None
            num_part = match.group(0)

            dec_obj = Decimal(num_part)
            flt_val = float(dec_obj)

            decimals = 0
            if "." in num_part:
                decimals = len(num_part.split(".")[1])

            return {
                "raw": raw_val,
                "cleaned": cleaned,
                "float_val": flt_val,
                "decimal_val": dec_obj,
                "decimals": decimals,
                "locale_used": locale
            }
        except Exception:
            return None
