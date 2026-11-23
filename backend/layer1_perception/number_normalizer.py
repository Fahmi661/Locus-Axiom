"""
LOCUS Dual-Locale Column-Level Number Normalizer.
Layer 1 Perception - Resolves Indonesian PUEBI ('12,45' / '1.250') vs SPSS ('12.45' / '.000').
"""

import re
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any


class NumberNormalizer:
    @staticmethod
    def clean_token(val_str: str) -> str:
        """Strips significance asterisks, parentheses, and leading operators."""
        if not val_str:
            return ""
        s = val_str.strip()
        # Remove markdown or asterisks like ***, **, *
        s = re.sub(r"[\*†‡]", "", s)
        # Remove wrapping parentheses if present
        s = re.sub(r"^\((.*?)\)$", r"\1", s)
        return s.strip()

    @classmethod
    def detect_column_locale(cls, column_values: List[str]) -> str:
        """
        Detects whether a column follows 'ID' (Indonesian PUEBI: comma decimal)
        or 'SPSS_US' (period decimal, leading dot like .000).
        """
        comma_decimal_votes = 0
        dot_decimal_votes = 0

        for raw in column_values:
            val = cls.clean_token(raw)
            if not val:
                continue

            # SPSS leading dot: e.g. .000, .452
            if re.match(r"^[+-]?\.\d+", val):
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
        column_locale: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Parses a raw cell string into numeric metadata.
        Returns: {
            'raw': raw_val,
            'float_val': float,
            'decimal_val': Decimal,
            'decimals': int,
            'locale_used': str
        }
        """
        cleaned = cls.clean_token(raw_val)
        if not cleaned:
            return None

        # SPSS leading dot or comma without zero: .000 -> 0.000, ,17 -> 0.17, -,45 -> -0.45, ,00 -> 0.0
        cleaned = re.sub(r"^([+-]?)\s*[,.](\d+)$", r"\g<1>0.\g<2>", cleaned)
        if cleaned.startswith("."):
            cleaned = "0" + cleaned
        elif cleaned.startswith("-."):
            cleaned = "-0" + cleaned[1:]
        elif cleaned.startswith(","):
            cleaned = "0." + cleaned[1:]
        elif cleaned.startswith("-,"):
            cleaned = "-0." + cleaned[2:]

        locale = column_locale
        if not locale or locale == "UNKNOWN":
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
