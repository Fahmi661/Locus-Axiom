"""
Unit Tests for LOCUS Deterministic Mathematical Solvers.
Ensures 100% accuracy on statistical formulas and consistency bounds.
"""

import pytest
from backend.layer2_core.stat_solvers import (
    StatcheckSolver,
    GuardedGrimSolver,
    GrimmerSolver,
    DebitSolver,
    TotalNSubgroupSweeper,
    ConfusionMatrixAndSumAuditor
)


def test_statcheck_t_pass():
    # t(28) = 2.45, reported p = 0.021
    res = StatcheckSolver.solve(
        test_type="t",
        stat_val=2.45,
        df1=28,
        p_reported=0.021,
        stat_str="2.45"
    )
    assert res["verdict"] == "PASS"
    assert res["p_interval"][0] <= 0.021 <= res["p_interval"][1]


def test_statcheck_decision_flip():
    # t(30) = 1.60 -> two-tailed p ≈ 0.120 (not significant, p >= 0.05)
    # but reported as 0.02 (significant, p < 0.05) -> DECISION FLIP
    res = StatcheckSolver.solve(
        test_type="t",
        stat_val=1.60,
        df1=30,
        p_reported=0.02,
        stat_str="1.60"
    )
    assert res["verdict"] == "DECISION_FLIP"


def test_statcheck_one_tailed_context():
    # Context contains 'satu arah'
    res = StatcheckSolver.solve(
        test_type="t",
        stat_val=2.00,
        df1=30,
        p_reported=0.027,
        stat_str="2.00",
        context_text="Pengujian dilakukan secara satu arah (one-tailed) dengan hipotesis terarah."
    )
    assert res["is_one_tailed"] is True
    assert res["verdict"] == "PASS"


def test_statcheck_apa_precision():
    res = StatcheckSolver.solve(
        test_type="F",
        stat_val=15.2,
        df1=2,
        df2=45,
        p_reported=0.000,
        stat_str="15.2"
    )
    assert res["verdict"] == "APA_PRECISION_NOTICE"


def test_guarded_grim_pass_and_fail():
    # With N=20 and 1 item: means must be multiples of 1/20 = 0.05
    # Mean = 3.45 is valid (3.45 * 20 = 69)
    res_pass = GuardedGrimSolver.solve(mean_val=3.45, n_sample=20, k_items=1, mean_str="3.45")
    assert res_pass["verdict"] == "PASS"

    # Mean = 3.47 is impossible on N=20 (nearest sum is 69 -> 3.45 or 70 -> 3.50)
    res_fail = GuardedGrimSolver.solve(mean_val=3.47, n_sample=20, k_items=1, mean_str="3.47")
    assert res_fail["verdict"] == "GRIM_INCONSISTENCY"


def test_guarded_grim_applicability():
    # Continuous variables shouldn't trigger GRIM
    res = GuardedGrimSolver.solve(mean_val=1250000.50, n_sample=30, is_discrete=False)
    assert res["verdict"] == "GRIM_NOT_APPLICABLE"


def test_grimmer_parity():
    # Valid N=20, mean=3.00 (S=60 is even).
    # With SD=1.03, (20-1)*1.03^2 + 60^2/20 = 19*1.0609 + 180 = 20.157 + 180 = 200.157
    # Nearest integer Q = 200 (even). S=60 (even). Q ≡ S (mod 2) -> PASSES GRIMMER!
    res_pass = GrimmerSolver.solve(mean_val=3.00, sd_val=1.03, n_sample=20, sd_str="1.03")
    assert res_pass["verdict"] == "PASS"

    # With SD=1.00, SS = 19*1 + 180 = 199 (odd). But S=60 (even). Parity mismatch -> GRIMMER_INCONSISTENCY!
    res_fail = GrimmerSolver.solve(mean_val=3.00, sd_val=1.00, n_sample=20, sd_str="1.00")
    assert res_fail["verdict"] == "GRIMMER_INCONSISTENCY"


def test_debit_binary():
    # In N=50, proportion 0.40 (k=20), binary SD = sqrt(50/49 * 0.4 * 0.6) = sqrt(0.24489) = 0.4948 ~ 0.49
    res_pass = DebitSolver.solve(prop_val=0.40, sd_val=0.49, n_sample=50, prop_str="0.40", sd_str="0.49")
    assert res_pass["verdict"] == "PASS"

    # Inconsistent SD
    res_fail = DebitSolver.solve(prop_val=0.40, sd_val=0.15, n_sample=50, prop_str="0.40", sd_str="0.15")
    assert res_fail["verdict"] == "DEBIT_INCONSISTENCY"


def test_total_n_subgroup_sweeper():
    # Total N = 50, mean1 = 3.45, mean2 = 3.50
    res = TotalNSubgroupSweeper.sweep(mean1=3.45, mean2=3.50, total_n=50)
    assert res["verdict"] == "PASS"
    assert res["feasible_count"] > 0


def test_confusion_matrix_auditor():
    # TP=80, FP=20, FN=10, TN=90
    # Precision = 80 / 100 = 0.80
    # Recall = 80 / 90 = 0.8889
    # Accuracy = 170 / 200 = 0.85
    res = ConfusionMatrixAndSumAuditor.audit_confusion_matrix(
        tp=80, fp=20, tn=90, fn=10,
        reported_precision=0.80,
        reported_recall=0.89,
        reported_accuracy=0.85
    )
    assert res["verdict"] == "PASS"


def test_percentage_sum():
    res_pass = ConfusionMatrixAndSumAuditor.audit_percentage_sum([25.4, 34.6, 40.0])
    assert res_pass["verdict"] == "PASS"

    res_fail = ConfusionMatrixAndSumAuditor.audit_percentage_sum([20.0, 30.0, 45.0]) # sum 95%
    assert res_fail["verdict"] == "SUM_PERCENTAGE_ERROR"


def test_tuple_verification_solver():
    from backend.layer2_core.stat_solvers import TupleVerificationSolver

    # 1. Exact match pass
    p1 = TupleVerificationSolver.verify_claimed_cell_number("1,49", 1.4874307, "Mean", "SQRTUKAP")
    assert p1["verdict"] == "PASS"

    # 2. Truncation rounding warning (2.07593 truncated to 2.07 instead of 2.08)
    w1 = TupleVerificationSolver.verify_claimed_cell_number("2,67", 2.6759333, "Mean", "SQRTPGLMN")
    assert w1["verdict"] == "WARN_TRUNCATION_ROUNDING"

    # 3. Transposition / Typo (5.48 typed as 5.84)
    t1 = TupleVerificationSolver.verify_claimed_cell_number("5,84", 5.48128, "Maximum", "PNGLM")
    assert t1["verdict"] == "DIGIT_TRANSPOSITION_TYPO"

    # 4. Direct cell contradiction (1.38 reported as 1.49)
    c1 = TupleVerificationSolver.verify_claimed_cell_number("1,49", 1.38495, "Mean", "SQRTKAP")
    assert c1["verdict"] == "DIRECT_CELL_CONTRADICTION"


def test_formula_eval_solver():
    from backend.layer2_core.stat_solvers import FormulaEvalSolver

    # 1. Zskewness pass: 0.317 / sqrt(6/68) = 1.067
    p1 = FormulaEvalSolver.audit_z_formula("Skewness", 0.317, 68, 1.067, 1.067)
    assert p1["verdict"] == "PASS"

    # 2. Zkurtosis narrative contradiction: formula output 0.71, text claims 1.05
    c1 = FormulaEvalSolver.audit_z_formula("Kurtosis", 0.420, 68, 0.71, 1.05)
    assert c1["verdict"] == "INLINE_FORMULA_NARRATIVE_CONTRADICTION"

    # 3. Zskewness calculation error: 0.267 / sqrt(6/68) reported as 1.063 (exact is 0.899)
    e1 = FormulaEvalSolver.audit_z_formula("Skewness", 0.267, 68, 1.063, 1.063)
    assert e1["verdict"] == "INLINE_FORMULA_CALC_ERROR"


def test_formula_sympy_ast_normalizer():
    from backend.layer2_core.stat_solvers import FormulaEvalSolver

    # Test Unicode square root and Indonesian comma decimal
    res = FormulaEvalSolver.evaluate_symbolic_expression("0,420 / √(24/68)")
    assert res["status"] == "SUCCESS"
    assert round(res["result"], 2) == 0.71

    # Test context variable substitution
    res_var = FormulaEvalSolver.evaluate_symbolic_expression("x / sqrt(6/N)", {"x": 0.317, "N": 68})
    assert res_var["status"] == "SUCCESS"
    assert round(res_var["result"], 3) == 1.067


def test_ocr_numeric_post_corrector():
    from backend.layer1_perception.ocr_fallback import OcrTableFallback

    corrected = OcrTableFallback.correct_numeric_ocr("O.425")
    assert corrected == "0.425"

    corrected_l = OcrTableFallback.correct_numeric_ocr("1.3l8")
    assert corrected_l == "1.318"
