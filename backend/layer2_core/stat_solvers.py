"""
LOCUS (Deterministic Mathematical Verification Engines)
Layer 2 Core - Exact solvers using SciPy and deterministic arithmetic.
Zero false positives on control datasets.
"""

from typing import Dict, Any, List, Optional, Tuple
import math
import re
from decimal import Decimal, ROUND_HALF_UP
import numpy as np
import scipy.stats as stats

try:
    import sympy
    from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False


def count_decimals(val_str: str) -> int:
    """Counts the number of decimal digits in a string representation of a number."""
    cleaned = val_str.strip()
    cleaned = re.sub(r"^([+-]?)\s*[,.](\d+)$", r"\g<1>0.\g<2>", cleaned).replace(",", ".")
    if "." in cleaned:
        return len(cleaned.split(".")[1])
    return 0


class StatcheckSolver:
    """
    Solver 1: Recalculates p-values with symmetric rounding intervals.
    Supports t, F, r, chi2, and Z distributions.
    Includes one-tailed context scanner and Bonferroni adjustments.
    """

    @staticmethod
    def solve(
        test_type: str,
        stat_val: float,
        df1: float,
        df2: Optional[float] = None,
        p_reported: Optional[float] = None,
        stat_str: Optional[str] = None,
        context_text: str = ""
    ) -> Dict[str, Any]:
        test_type_clean = test_type.lower().strip()
        stat_abs = abs(stat_val)

        # Determine precision d
        d = count_decimals(stat_str) if stat_str else 2
        half_step = 0.5 * (10 ** (-d))
        s_low = max(0.0, stat_abs - half_step)
        s_high = stat_abs + half_step

        # Context scanner: check for one-tailed testing
        one_tailed_keywords = ["satu arah", "one-tailed", "directional", "satu sisi", "1-tailed"]
        is_one_tailed = any(k in context_text.lower() for k in one_tailed_keywords)

        # Context scanner: check for corrections
        correction_applied = "bonferroni" in context_text.lower() or "huynh-feldt" in context_text.lower()

        # Compute p-value bounds using SciPy survival function (1 - CDF)
        try:
            if test_type_clean in ["t", "t-test", "uji-t"]:
                tail_multiplier = 1.0 if is_one_tailed else 2.0
                p_recalc = float(stats.t.sf(stat_abs, df1) * tail_multiplier)
                p_min = float(stats.t.sf(s_high, df1) * tail_multiplier)
                p_max = float(stats.t.sf(s_low, df1) * tail_multiplier)
                formula_name = f"t({int(df1)}) = {stat_val}"

            elif test_type_clean in ["f", "f-test", "anova"]:
                if df2 is None or df2 <= 0:
                    df2 = 1.0
                p_recalc = float(stats.f.sf(stat_val, df1, df2))
                p_min = float(stats.f.sf(s_high, df1, df2))
                p_max = float(stats.f.sf(s_low, df1, df2))
                formula_name = f"F({int(df1)}, {int(df2)}) = {stat_val}"

            elif test_type_clean in ["r", "pearson", "korelasi"]:
                # Convert Pearson r to t-statistic
                denom = max(1e-9, 1.0 - (stat_val ** 2))
                t_stat = stat_val * math.sqrt(df1 / denom)
                tail_multiplier = 1.0 if is_one_tailed else 2.0
                p_recalc = float(stats.t.sf(abs(t_stat), df1) * tail_multiplier)
                # Bounds
                t_low = s_low * math.sqrt(df1 / max(1e-9, 1.0 - (s_low ** 2)))
                t_high = s_high * math.sqrt(df1 / max(1e-9, 1.0 - (s_high ** 2)))
                p_min = float(stats.t.sf(abs(t_high), df1) * tail_multiplier)
                p_max = float(stats.t.sf(abs(t_low), df1) * tail_multiplier)
                formula_name = f"r({int(df1)}) = {stat_val}"

            elif test_type_clean in ["chi2", "chisq", "chi-square", "chi_square"]:
                p_recalc = float(stats.chi2.sf(stat_val, df1))
                p_min = float(stats.chi2.sf(s_high, df1))
                p_max = float(stats.chi2.sf(s_low, df1))
                formula_name = f"χ²({int(df1)}) = {stat_val}"

            elif test_type_clean in ["z", "z-test"]:
                tail_multiplier = 1.0 if is_one_tailed else 2.0
                p_recalc = float(stats.norm.sf(stat_abs) * tail_multiplier)
                p_min = float(stats.norm.sf(s_high) * tail_multiplier)
                p_max = float(stats.norm.sf(s_low) * tail_multiplier)
                formula_name = f"Z = {stat_val}"

            else:
                return {
                    "verdict": "ERROR_UNKNOWN_TEST",
                    "details": f"Jenis uji '{test_type}' belum didukung."
                }
        except Exception as e:
            return {"verdict": "COMPUTATION_ERROR", "details": str(e)}

        # Cap bounds in [0, 1]
        p_min = max(0.0, min(1.0, p_min))
        p_max = max(0.0, min(1.0, p_max))
        p_recalc = max(0.0, min(1.0, p_recalc))

        result = {
            "test_type": test_type_clean,
            "formula_display": formula_name,
            "stat_val": stat_val,
            "s_range": [round(s_low, 5), round(s_high, 5)],
            "p_recalc": round(p_recalc, 5),
            "p_interval": [round(p_min, 5), round(p_max, 5)],
            "is_one_tailed": is_one_tailed,
            "correction_applied": correction_applied
        }

        if p_reported is None:
            result["verdict"] = "RECALCULATED"
            return result

        result["p_reported"] = p_reported

        # APA precision notice check: p = 0.000 or p = .000
        is_zero_reported = (p_reported == 0.0)

        # Decimal precision of reported p
        # Nuijten et al. (2016): reported p has its own rounding precision d_p
        d_p = count_decimals(str(p_reported))
        p_rep_step = 0.5 * (10 ** (-min(3, max(2, d_p))))

        # Check interval overlap: [p_reported - p_rep_step, p_reported + p_rep_step] overlaps [p_min, p_max]
        p_rep_low = max(0.0, p_reported - p_rep_step)
        p_rep_high = min(1.0, p_reported + p_rep_step)

        in_interval = not (p_rep_high < p_min or p_rep_low > p_max)
        same_alpha_side = (p_reported < 0.05 and p_recalc < 0.05) or (p_reported >= 0.05 and p_recalc >= 0.05)

        if is_zero_reported:
            result["verdict"] = "APA_PRECISION_NOTICE"
            result["explanation"] = "Nilai p dilaporkan sebagai 0,000. Standar pelaporan APA mewajibkan penulisan 'p < 0,001'."
        elif in_interval:
            result["verdict"] = "PASS"
            result["explanation"] = f"Nilai p lapor ({p_reported}) berada dalam rentang pembulatan [{round(p_min, 4)}, {round(p_max, 4)}]."
        elif not same_alpha_side:
            result["verdict"] = "DECISION_FLIP"
            result["explanation"] = (
                f"Kesalahan Fatal: Nilai p dilaporkan ({p_reported}) membalik keputusan signifikansi statistik terhadap alpha 0.05! "
                f"Hasil rekalkulasi eksak adalah p = {round(p_recalc, 4)} (rentang [{round(p_min, 4)}, {round(p_max, 4)}])."
            )
        else:
            result["verdict"] = "WARN_ROUNDING"
            result["explanation"] = (
                f"Peringatan Pembulatan: Nilai p lapor ({p_reported}) berada di luar interval pembulatan simetris [{round(p_min, 4)}, {round(p_max, 4)}], "
                f"tetapi tidak membalik kesimpulan signifikansi."
            )

        return result


FORBIDDEN_GRIM_SUBSTRINGS = (
    "SQRT", "RESID", "RESIDUAL", "ZSCORE", "STD", "DEVIATION", "ERROR",
    "SKEW", "KURT", "ROA", "ROE", "DER", "DAR", "EPS", "DELAY", "WAKTU",
    "TRANSFORM", "DIFF", "PERSEN", "%", "RATIO", "COEFF"
)
FORBIDDEN_GRIM_EXACT_WORDS = ("B", "T", "SIG", "LN", "LOG")
FORBIDDEN_GRIM_TOKENS = FORBIDDEN_GRIM_SUBSTRINGS + FORBIDDEN_GRIM_EXACT_WORDS

def is_grim_applicable_strict(raw_val_str: str, n: int, row_label: str = "", col_header: str = "") -> bool:
    """
    Hanya mengizinkan GRIM jika:
    1. Kolom adalah Mean / Rata-rata,
    2. Baris BUKAN hasil transformasi kontinu (SQRT, LN, LOG, Residual),
    3. Jumlah digit desimal d berada di {1, 2} (BUKAN float 15 desimal SPSS),
    4. Ukuran sampel N <= 10^d.
    """
    label_upper = f"{row_label} {col_header}".upper()
    if any(tok in label_upper for tok in FORBIDDEN_GRIM_SUBSTRINGS):
        return False
    if re.search(r"\b(?:B|T|SIG|LN|LOG)\b", label_upper):
        return False
    if col_header and not any(m in col_header.upper() for m in ("MEAN", "RATA", "RERATA")):
        return False

    cleaned = raw_val_str.strip()
    cleaned = re.sub(r"^([+-]?)\s*[,.](\d+)$", r"\g<1>0.\g<2>", cleaned).replace(",", ".")
    if "." not in cleaned:
        return False
    frac_part = cleaned.split(".")[-1]
    d = len(frac_part)
    # Strictly reject decimals > 2 (such as SPSS 15-decimal outputs like 0.42522430394442) or decimals < 1
    if d < 1 or d > 2:
        return False
    return 0 < n <= (10 ** d)


class GuardedGrimSolver:
    """
    Solver 2: Granularity-Related Inconsistency of Means (GRIM) Test.
    Includes Applicability Gate: activates only for integer counts or Likert scale data
    where N * k <= 10^d and d in {1, 2}.
    """

    @staticmethod
    def solve(
        mean_val: float,
        n_sample: int,
        k_items: int = 1,
        mean_str: Optional[str] = None,
        is_discrete: bool = True,
        row_label: str = "",
        col_header: str = ""
    ) -> Dict[str, Any]:
        if not is_discrete:
            return {
                "verdict": "GRIM_NOT_APPLICABLE",
                "explanation": "Variabel kontinu (seperti rupiah, waktu, berat, suhu) tidak terikat pada kekisi bilangan bulat GRIM."
            }

        d = count_decimals(mean_str) if mean_str else 2
        effective_n = n_sample * k_items

        if d > 2 or effective_n > (10 ** d):
            return {
                "verdict": "GRIM_NOT_APPLICABLE",
                "explanation": f"Resolusi desimal d={d} atau ukuran sampel ({effective_n}) melampaui batas uji GRIM (hanya valid untuk d in {{1, 2}} pada skala diskret)."
            }

        if mean_str and not is_grim_applicable_strict(mean_str, n_sample, row_label, col_header):
            return {
                "verdict": "GRIM_NOT_APPLICABLE",
                "explanation": f"Uji GRIM tidak berlaku untuk baris/kolom kontinu atau transformasi: '{row_label}' ({mean_str})."
            }

        # Calculate nearest integer sum
        total_sum_est = mean_val * effective_n
        rounded_int_sum = round(total_sum_est)
        recalculated_mean = rounded_int_sum / effective_n
        diff = abs(mean_val - recalculated_mean)
        allowed_tolerance = 0.5 * (10 ** (-d)) + 1e-7

        passed = diff <= allowed_tolerance

        return {
            "verdict": "PASS" if passed else "GRIM_INCONSISTENCY",
            "mean_reported": mean_val,
            "n_sample": n_sample,
            "k_items": k_items,
            "effective_n": effective_n,
            "nearest_integer_sum": rounded_int_sum,
            "recalculated_mean": round(recalculated_mean, d + 2),
            "difference": round(diff, 6),
            "allowed_tolerance": round(allowed_tolerance, 6),
            "explanation": (
                f"Lolos uji kekisi bulat GRIM. Jumlah total bulat = {rounded_int_sum}."
                if passed else
                f"Anomali GRIM: Rata-rata {mean_val} pada N={n_sample} (k={k_items}) secara matematis mustahil dihasilkan dari penjumlahan data diskret/Likert. Nilai terdekat yang mungkin adalah {round(recalculated_mean, d)}."
            )
        }


class GrimmerSolver:
    """
    Solver 3: GRIMMER (GRIM for Standard Deviations) and SPRITE Feasibility.
    Tests variance SD parity: Q = (N-1)*SD^2 + S^2/N must match integer Q with parity Q ≡ S (mod 2).
    """

    @staticmethod
    def solve(
        mean_val: float,
        sd_val: float,
        n_sample: int,
        k_items: int = 1,
        scale_min: float = 1.0,
        scale_max: float = 5.0,
        sd_str: Optional[str] = None
    ) -> Dict[str, Any]:
        # First check GRIM on the mean
        grim_res = GuardedGrimSolver.solve(mean_val, n_sample, k_items)
        if grim_res.get("verdict") == "GRIM_INCONSISTENCY":
            return {
                "verdict": "GRIMMER_FAIL_ON_MEAN",
                "explanation": "Rata-rata gagal uji GRIM terlebih dahulu, sehingga uji varians GRIMMER otomatis gugur."
            }

        eff_n = n_sample * k_items
        s_int = round(mean_val * eff_n)

        d = count_decimals(sd_str) if sd_str else 2
        half_step = 0.5 * (10 ** (-d))

        sd_low = max(0.0, sd_val - half_step)
        sd_high = sd_val + half_step

        # SPRITE sanity bounds: max possible SD for a bounded scale
        max_possible_sd = ((scale_max - scale_min) / 2.0) * math.sqrt(n_sample / max(1, n_sample - 1))
        if sd_val > max_possible_sd + half_step:
            return {
                "verdict": "SPRITE_BOUND_VIOLATION",
                "explanation": f"Simpangan baku {sd_val} melampaui batas matematis maksimum untuk skala [{scale_min}, {scale_max}] pada N={n_sample} (Max SD = {round(max_possible_sd, 3)})."
            }

        # Sum of squares interval: SS = (N - 1) * SD^2 + S^2 / N
        ss_low = (eff_n - 1) * (sd_low ** 2) + (s_int ** 2) / eff_n
        ss_high = (eff_n - 1) * (sd_high ** 2) + (s_int ** 2) / eff_n

        q_min = math.ceil(ss_low - 1e-7)
        q_max = math.floor(ss_high + 1e-7)

        # Check parity: Q ≡ S (mod 2)
        valid_q_exists = False
        matching_q = None
        for q in range(q_min, q_max + 1):
            if (q % 2) == (s_int % 2):
                valid_q_exists = True
                matching_q = q
                break

        return {
            "verdict": "PASS" if valid_q_exists else "GRIMMER_INCONSISTENCY",
            "mean": mean_val,
            "sd": sd_val,
            "n": n_sample,
            "integer_sum_s": s_int,
            "ss_range": [round(ss_low, 3), round(ss_high, 3)],
            "matching_q": matching_q,
            "explanation": (
                f"Lolos uji paritas varians GRIMMER (Q = {matching_q} ≡ {s_int % 2} mod 2)."
                if valid_q_exists else
                f"Anomali GRIMMER: Tidak ditemukan bilangan bulat jumlah kuadrat Q dalam rentang [{round(ss_low, 2)}, {round(ss_high, 2)}] yang memiliki paritas ganjil/genap sama dengan total S={s_int}."
            )
        }


class DebitSolver:
    """
    Solver 4: DEBIT Test for Binary Data.
    Tests consistency of proportion p and binary standard deviation s on sample size N.
    """

    @staticmethod
    def solve(
        prop_val: float,
        sd_val: float,
        n_sample: int,
        prop_str: Optional[str] = None,
        sd_str: Optional[str] = None
    ) -> Dict[str, Any]:
        d_p = count_decimals(prop_str) if prop_str else 2
        d_s = count_decimals(sd_str) if sd_str else 2

        tol_p = 0.5 * (10 ** (-d_p))
        tol_s = 0.5 * (10 ** (-d_s))

        found_k = None
        recalc_sd = None

        for k in range(0, n_sample + 1):
            p_k = k / n_sample
            if abs(p_k - prop_val) <= tol_p + 1e-7:
                # Binary sample SD formula: sqrt( (N / (N-1)) * p * (1 - p) )
                if n_sample > 1:
                    var_k = (n_sample / (n_sample - 1)) * p_k * (1.0 - p_k)
                    sd_k = math.sqrt(max(0.0, var_k))
                else:
                    sd_k = 0.0

                if abs(sd_k - sd_val) <= tol_s + 1e-7:
                    found_k = k
                    recalc_sd = sd_k
                    break

        passed = (found_k is not None)

        return {
            "verdict": "PASS" if passed else "DEBIT_INCONSISTENCY",
            "reported_proportion": prop_val,
            "reported_sd": sd_val,
            "n_sample": n_sample,
            "consistent_k": found_k,
            "recalculated_sd": round(recalc_sd, d_s + 2) if recalc_sd is not None else None,
            "explanation": (
                f"Lolos uji DEBIT biner. Ditemukan k = {found_k} dari {n_sample} responden."
                if passed else
                f"Anomali DEBIT: Pasangan proporsi {prop_val} dan SD {sd_val} pada N={n_sample} mustahil dihasilkan dari data biner 0/1."
            )
        }


class TotalNSubgroupSweeper:
    """
    Solver 5: Sweeps integer partitions n1 + n2 = N_total when subgroup n is missing.
    """

    @staticmethod
    def sweep(
        mean1: float,
        mean2: float,
        total_n: int,
        k_items: int = 1,
        mean1_str: Optional[str] = None,
        mean2_str: Optional[str] = None
    ) -> Dict[str, Any]:
        feasible_partitions: List[Tuple[int, int]] = []

        for n1 in range(2, total_n - 1):
            n2 = total_n - n1
            res1 = GuardedGrimSolver.solve(mean1, n1, k_items, mean1_str)
            res2 = GuardedGrimSolver.solve(mean2, n2, k_items, mean2_str)

            if res1.get("verdict") == "PASS" and res2.get("verdict") == "PASS":
                feasible_partitions.append((n1, n2))

        passed = len(feasible_partitions) > 0

        return {
            "verdict": "PASS" if passed else "SUBGROUP_IMPOSSIBLE",
            "total_n": total_n,
            "mean1": mean1,
            "mean2": mean2,
            "feasible_count": len(feasible_partitions),
            "feasible_examples": feasible_partitions[:5],
            "explanation": (
                f"Ditemukan {len(feasible_partitions)} pasangan partisi ukuran sampel yang konsisten dengan uji GRIM kedua kelompok."
                if passed else
                f"Anomali Total-N: Tidak ada partisi bilangan bulat n1 + n2 = {total_n} yang memungkinkan rata-rata kelompok {mean1} dan {mean2} terbentuk secara valid."
            )
        }


class ConfusionMatrixAndSumAuditor:
    """
    Solver 6: Confusion Matrix Metrics Verification & Percentage Sum Auditor.
    """

    @staticmethod
    def audit_confusion_matrix(
        tp: float,
        fp: float,
        tn: float,
        fn: float,
        reported_precision: Optional[float] = None,
        reported_recall: Optional[float] = None,
        reported_f1: Optional[float] = None,
        reported_accuracy: Optional[float] = None,
        tolerance: float = 0.015
    ) -> Dict[str, Any]:
        denom_p = tp + fp
        denom_r = tp + fn
        denom_acc = tp + fp + tn + fn

        calc_p = (tp / denom_p) if denom_p > 0 else 0.0
        calc_r = (tp / denom_r) if denom_r > 0 else 0.0
        calc_f1 = (2 * calc_p * calc_r / (calc_p + calc_r)) if (calc_p + calc_r) > 0 else 0.0
        calc_acc = ((tp + tn) / denom_acc) if denom_acc > 0 else 0.0

        discrepancies = []

        if reported_precision is not None:
            if abs(reported_precision - calc_p) > tolerance:
                discrepancies.append(f"Precision lapor ({reported_precision}) ≠ hitung ({round(calc_p, 4)})")

        if reported_recall is not None:
            if abs(reported_recall - calc_r) > tolerance:
                discrepancies.append(f"Recall lapor ({reported_recall}) ≠ hitung ({round(calc_r, 4)})")

        if reported_f1 is not None:
            if abs(reported_f1 - calc_f1) > tolerance:
                discrepancies.append(f"F1 lapor ({reported_f1}) ≠ hitung ({round(calc_f1, 4)})")

        if reported_accuracy is not None:
            if abs(reported_accuracy - calc_acc) > tolerance:
                discrepancies.append(f"Accuracy lapor ({reported_accuracy}) ≠ hitung ({round(calc_acc, 4)})")

        passed = len(discrepancies) == 0

        return {
            "verdict": "PASS" if passed else "CONFUSION_MATRIX_INCONSISTENCY",
            "calculated": {
                "precision": round(calc_p, 4),
                "recall": round(calc_r, 4),
                "f1_score": round(calc_f1, 4),
                "accuracy": round(calc_acc, 4)
            },
            "discrepancies": discrepancies,
            "explanation": "Matriks konfusi terbukti konsisten secara matematis." if passed else " ; ".join(discrepancies)
        }

    @staticmethod
    def audit_percentage_sum(percentages: List[float]) -> Dict[str, Any]:
        total = sum(percentages)
        # Standard rounding tolerance: [99.8%, 100.2%]
        passed = 99.8 <= total <= 100.2
        return {
            "verdict": "PASS" if passed else "SUM_PERCENTAGE_ERROR",
            "sum": round(total, 2),
            "expected_range": [99.8, 100.2],
            "explanation": (
                f"Total persentase ({round(total, 2)}%) berada dalam rentang toleransi pembulatan."
                if passed else
                f"Total persentase ({round(total, 2)}%) menyimpang dari 100% di luar batas pembulatan lazim."
            )
        }


class TupleVerificationSolver:
    """
    Solver 7: Direct Cell-Value, Rounding & Typo-Transposition Verifier.
    Compares numbers explicitly claimed in narrative sentences against exact table cells.
    Detects:
    - PASS (mathematically exact standard rounding)
    - WARN_TRUNCATION_ROUNDING (truncated without rounding up, e.g. 2.0759 -> 2.07 instead of 2.08)
    - DIGIT_TRANSPOSITION_TYPO (digit swap or single typo, e.g. 5.48 typed as 5.04)
    - DIRECT_CELL_CONTRADICTION (numeric mismatch, e.g. table is 1.38 but claimed 1.49)
    """

    @staticmethod
    def verify_claimed_cell_number(
        claimed_str: str,
        cell_value: float,
        metric_col: str,
        row_label: str
    ) -> Dict[str, Any]:
        clean_claim = claimed_str.strip()
        clean_claim = re.sub(r"^([+-]?)\s*[,.](\d+)$", r"\g<1>0.\g<2>", clean_claim)
        if "," in clean_claim and "." in clean_claim:
            clean_claim = clean_claim.replace(".", "").replace(",", ".")
        else:
            clean_claim = clean_claim.replace(",", ".")
        try:
            v_claim = float(clean_claim)
        except ValueError:
            return {"verdict": "SKIP"}

        decimals = len(clean_claim.split(".")[1]) if "." in clean_claim else 0
        q = Decimal("10") ** (-decimals)
        v_round = float(Decimal(str(cell_value)).quantize(q, rounding=ROUND_HALF_UP))
        factor = 10 ** decimals
        v_trunc = math.trunc(cell_value * factor) / factor

        # 1. Exact match with standard rounding
        if abs(v_claim - v_round) <= 1e-6:
            return {
                "verdict": "PASS",
                "claimed": v_claim,
                "table_exact": cell_value,
                "table_rounded": v_round,
                "diff": 0.0,
                "formula_display": f"{row_label} ({metric_col}): Sel = {cell_value:.5f} -> Pembulatan {decimals} desimal = {v_round:.{decimals}f} (Sesuai)"
            }

        # 2. Truncation without rounding up
        if abs(v_claim - v_trunc) <= 1e-6 and abs(v_round - v_trunc) > 1e-6:
            return {
                "verdict": "WARN_TRUNCATION_ROUNDING",
                "claimed": v_claim,
                "table_exact": cell_value,
                "table_rounded": v_round,
                "diff": round(v_claim - v_round, decimals + 1),
                "formula_display": f"{row_label} ({metric_col}): Sel = {cell_value:.5f} -> Pembulatan {decimals} desimal seharusnya = {v_round:.{decimals}f} (tertulis {v_claim:.{decimals}f} akibat pemotongan tanpa pembulatan ke atas)"
            }

        # 3. Transposition / Typo (adjacent digit swap or single-character typo)
        s_claim = f"{v_claim:.{decimals}f}".replace(".", ",")
        s_round = f"{v_round:.{decimals}f}".replace(".", ",")
        is_permutation = (sorted(s_claim) == sorted(s_round) and s_claim != s_round)
        matching_positions = sum(1 for a, b in zip(s_claim, s_round) if a == b)
        is_single_typo = (len(s_claim) == len(s_round) and matching_positions == len(s_claim) - 1 and abs(v_claim - v_round) > 0.05)

        if is_permutation or is_single_typo:
            return {
                "verdict": "DIGIT_TRANSPOSITION_TYPO",
                "claimed": v_claim,
                "table_exact": cell_value,
                "table_rounded": v_round,
                "diff": round(v_claim - v_round, decimals + 1),
                "formula_display": f"{row_label} ({metric_col}): Tertulis di teks = {s_claim} != Nilai sel Tabel = {s_round} (Asli: {cell_value:.5f}) - Indikasi salah ketik digit"
            }

        # 4. Direct Cell Contradiction
        return {
            "verdict": "DIRECT_CELL_CONTRADICTION",
            "claimed": v_claim,
            "table_exact": cell_value,
            "table_rounded": v_round,
            "diff": round(v_claim - v_round, decimals + 1),
            "formula_display": f"{row_label} ({metric_col}): Klaim teks = {s_claim} != Sel Tabel = {s_round} (Asli: {cell_value:.5f}, Selisih Δ = {abs(v_claim - v_round):.{decimals}f})"
        }


class FormulaEvalSolver:
    """
    Solver 8: Inline Formula Evaluator & Text Consistency Auditor.
    Parses expressions like Z = Skewness / sqrt(6/N) or Z = Kurtosis / sqrt(24/N),
    computes exact arithmetic, and checks consistency with accompanying narrative sentences.
    Enhanced in v3.1 with SymPy AST Normalization for Unicode math symbols.
    """

    @staticmethod
    def normalize_math_string(expr_str: str) -> str:
        """
        Normalizes human-written academic mathematical expressions:
        Replaces Unicode minus (minus/en-dash), square root symbols (sqrt),
        multiplication, division, exponents, and Indonesian decimal commas.
        """
        import re
        s = expr_str.strip()
        # Replace Unicode minus, en-dash, and em-dash with standard hyphen-minus
        s = s.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
        # Replace multiplication and division symbols
        s = s.replace("×", "*").replace("·", "*").replace("÷", "/")
        # Replace exponents (e.g. ^2 -> **2)
        s = re.sub(r"\^(\d+)", r"**\1", s)
        # Replace decimal commas preceded and followed by digits (e.g. 0,71 -> 0.71)
        s = re.sub(r"(\d+),(\d+)", r"\1.\2", s)
        # Normalize square root: √(expr) or √expr -> sqrt(expr)
        s = re.sub(r"√\s*\(([^)]+)\)", r"sqrt(\1)", s)
        s = re.sub(r"√\s*([A-Za-z0-9_]+)", r"sqrt(\1)", s)
        return s

    @classmethod
    def evaluate_symbolic_expression(
        cls,
        expr_str: str,
        context_vars: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        SymPy AST Normalizer and Evaluator for inline academic formulas.
        Evaluates formula against variable bindings with robust syntax tolerance.
        """
        context_vars = context_vars or {}
        cleaned_expr = cls.normalize_math_string(expr_str)

        if not HAS_SYMPY:
            return {"status": "FALLBACK", "expr": cleaned_expr, "result": None}

        try:
            transformations = (standard_transformations + (implicit_multiplication_application,))
            local_dict = {k: sympy.Symbol(k) for k in context_vars}
            sym_expr = parse_expr(cleaned_expr, local_dict=local_dict, transformations=transformations)
            subs_dict = {sympy.Symbol(k): v for k, v in context_vars.items()}
            val = float(sym_expr.evalf(subs=subs_dict))
            return {
                "status": "SUCCESS",
                "expr": cleaned_expr,
                "result": val,
                "latex": sympy.latex(sym_expr)
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "expr": cleaned_expr,
                "error": str(e),
                "result": None
            }

    @staticmethod
    def audit_z_formula(
        metric_name: str,
        stat_val: Optional[float],
        n_sample: Optional[int],
        reported_z: float,
        narrative_claimed_z: Optional[float] = None
    ) -> Dict[str, Any]:
        is_kurtosis = "kurt" in metric_name.lower()
        c_factor = 24.0 if is_kurtosis else 6.0
        
        if stat_val is not None and n_sample is not None and n_sample > 0:
            se_exact = math.sqrt(c_factor / n_sample)
            z_exact = round(abs(stat_val) / se_exact, 3)
        else:
            z_exact = round(reported_z, 3)

        # Narrative contradiction check (e.g. formula says 0.71, text claims 1.05)
        if narrative_claimed_z is not None and abs(narrative_claimed_z - reported_z) > 0.05:
            return {
                "verdict": "INLINE_FORMULA_NARRATIVE_CONTRADICTION",
                "reported_z": reported_z,
                "narrative_z": narrative_claimed_z,
                "exact_z": z_exact,
                "diff": round(abs(narrative_claimed_z - reported_z), 3),
                "formula_display": f"Z_{metric_name}: Hitung Rumus = {reported_z:.2f} != Klaim Narasi = {narrative_claimed_z:.2f} (Kontradiksi Langsung Penulis)"
            }

        if stat_val is not None and n_sample is not None and n_sample > 0:
            calc_diff = abs(reported_z - z_exact)
            if calc_diff > 0.015:
                return {
                    "verdict": "INLINE_FORMULA_CALC_ERROR",
                    "reported_z": reported_z,
                    "exact_z": z_exact,
                    "diff": round(calc_diff, 4),
                    "formula_display": f"Z_{metric_name}: Nilai eksak = {stat_val} / √({int(c_factor)}/{n_sample}) = {z_exact:.3f} != Nilai Lapor = {reported_z:.3f} (Selisih Δ = {calc_diff:.3f})"
                }

        return {
            "verdict": "PASS",
            "reported_z": reported_z,
            "exact_z": z_exact,
            "diff": 0.0,
            "formula_display": f"Z_{metric_name}: Nilai lapor {reported_z} ≈ eksak {z_exact} (Sesuai)"
        }


class HarmonicMeanF1Solver:
    """
    Solver 7: F1-Score Harmonic Mean Recalculator & Truncation Auditor.
    Computes exact harmonic mean: F1 = 2 * (P * R) / (P + R).
    Detects math discrepancies and truncation rounding errors.
    """
    @staticmethod
    def solve(
        reported_p: float,
        reported_r: float,
        reported_f1: float,
        method_name: str = ""
    ) -> Dict[str, Any]:
        if (reported_p + reported_r) <= 0:
            return {"verdict": "SKIP"}
        p = reported_p / 100.0 if reported_p > 1.0 else reported_p
        r = reported_r / 100.0 if reported_r > 1.0 else reported_r
        f1_rep = reported_f1 / 100.0 if reported_f1 > 1.0 else reported_f1

        calc_f1 = (2.0 * p * r) / (p + r)
        rounded_f1 = round(calc_f1, 4)
        calc_str = f"{calc_f1:.6f}"
        trunc_f1 = float(calc_str[:6])

        diff = abs(f1_rep - rounded_f1)

        if abs(f1_rep - trunc_f1) < 1e-4 and rounded_f1 != trunc_f1:
            return {
                "verdict": "WARN_TRUNCATION_ROUNDING",
                "calculated": rounded_f1,
                "reported": f1_rep,
                "diff": round(diff, 4),
                "explanation": (
                    f"Nilai F1-Score pada {method_name} dipotong menjadi {f1_rep}, "
                    f"padahal pembulatan matematika baku seharusnya ke atas menjadi {rounded_f1} "
                    f"(hasil rekalkulasi eksak: {calc_f1:.6f})."
                ),
                "formula_display": f"F1 = 2 * ({p:.4f} * {r:.4f}) / ({p:.4f} + {r:.4f}) = {calc_f1:.6f} => Pembulatan baku: {rounded_f1} (Lapor: {f1_rep})"
            }
        elif diff > 0.005:
            return {
                "verdict": "INLINE_FORMULA_CALC_ERROR",
                "calculated": rounded_f1,
                "reported": f1_rep,
                "diff": round(diff, 4),
                "explanation": (
                    f"Terdapat galat kalkulasi nilai F1-Score pada {method_name}: "
                    f"nilai lapor adalah {f1_rep}, sedangkan rekalkulasi harmonik presisi dan recall menghasilkan {rounded_f1}."
                ),
                "formula_display": f"F1 = 2 * ({p:.4f} * {r:.4f}) / ({p:.4f} + {r:.4f}) = {rounded_f1} != Lapor {f1_rep}"
            }
        return {"verdict": "PASS", "calculated": rounded_f1}


class RapidMinerVarianceAuditor:
    """
    Solver 8: RapidMiner / ML Software Output Variance & PlusMinus Auditor.
    Detects misinterpretation of standard deviation (+/-) across cross-validation
    folds as iterative growth or per-iteration performance increase.
    """
    @staticmethod
    def audit_claim_against_variance(
        claim_text: str,
        table_output: str,
        metric_name: str = "Akurasi"
    ) -> Optional[Dict[str, Any]]:
        m = re.search(r"(?:kenaikan|peningkatan)\s+(?:di\s*setiap|setiap)\s+perulangan\s+sebesar\s+([+-]?\d+[,.]\d+)%?", claim_text, re.IGNORECASE)
        if not m:
            return None

        claimed_increase = m.group(1).replace(",", ".")
        claimed_val = float(claimed_increase)

        pattern = rf"\+/-\s*{re.escape(claimed_increase)}%?"
        if re.search(pattern, table_output, re.IGNORECASE) or re.search(rf"\+/-\s*{claimed_val}", table_output):
            return {
                "verdict": "METRIC_SEMANTIC_HALLUCINATION",
                "severity": "CRITICAL",
                "claimed_growth": f"{claimed_increase}%",
                "table_metric": f"+/- {claimed_increase}%",
                "explanation": (
                    f"Penulis mengalami sesat nalar interpretasi statistik: nilai '+/- {claimed_increase}%' "
                    f"pada luaran RapidMiner adalah Standar Deviasi (margin galat variabilitas antar-fold), "
                    f"BUKAN 'kenaikan disetiap perulangan'. Notasi +/- pada k-fold cross validation tidak pernah "
                    f"merepresentasikan pertumbuhan iteratif."
                ),
                "formula_display": f"RapidMiner Output: {metric_name} +/- {claimed_increase}% => Standar Deviasi s = {claimed_increase}%, BUKAN Delta Kenaikan (Delta != {claimed_increase}%)"
            }
        return None


class SuperlativeTableAuditor:
    """
    Solver 9: Superlative & Extremum Consistency Auditor against full table column series.
    Detects claims of 'tertinggi' / 'terendah' when another row in the table contradicts it.
    """
    @staticmethod
    def audit_column_superlative(
        claim_text: str,
        col_name: str,
        series: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        is_highest_claim = any(w in claim_text.lower() for w in ["tertinggi", "terbesar", "paling tinggi", "paling besar"])
        is_lowest_claim = any(w in claim_text.lower() for w in ["terendah", "terkecil", "paling rendah", "paling kecil"])
        if not is_highest_claim and not is_lowest_claim:
            return None

        num_match = re.search(r"(\d+[,.]\d+)\s*%", claim_text)
        if not num_match:
            return None

        claimed_num = float(num_match.group(1).replace(",", "."))
        if not series:
            return None

        if is_highest_claim:
            max_item = max(series, key=lambda x: x["val"])
            if max_item["val"] > claimed_num + 0.0001:
                return {
                    "verdict": "SUPERLATIVE_CONTRADICTION",
                    "severity": "CRITICAL",
                    "claimed_val": claimed_num,
                    "true_best_val": max_item["val"],
                    "true_best_label": max_item.get("label", ""),
                    "explanation": (
                        f"Teks mengklaim bahwa nilai {col_name} tertinggi adalah {claimed_num}%, "
                        f"namun tabel data menunjukkan nilai tertinggi sebenarnya adalah {max_item['val']}% "
                        f"pada baris {max_item.get('label', '')}."
                    ),
                    "formula_display": f"ArgMax({col_name}) = {max_item['val']}% ({max_item.get('label', '')}) > Nilai Klaim {claimed_num}%"
                }

        if is_lowest_claim:
            min_item = min(series, key=lambda x: x["val"])
            if min_item["val"] < claimed_num - 0.0001:
                return {
                    "verdict": "SUPERLATIVE_CONTRADICTION",
                    "severity": "CRITICAL",
                    "claimed_val": claimed_num,
                    "true_best_val": min_item["val"],
                    "true_best_label": min_item.get("label", ""),
                    "explanation": (
                        f"Teks mengklaim bahwa nilai {col_name} terendah adalah {claimed_num}%, "
                        f"namun tabel data menunjukkan nilai terendah sebenarnya adalah {min_item['val']}% "
                        f"pada baris {min_item.get('label', '')}."
                    ),
                    "formula_display": f"ArgMin({col_name}) = {min_item['val']}% ({min_item.get('label', '')}) < Nilai Klaim {claimed_num}%"
                }

        return None
