"""
Regression unit tests for LOCUS v3.5.1 Hardening.
Verifies negation polarity, citation year extraction, Statcheck ANOVA decision flip,
PII redactor decimal preservation, and guarded GRIM sample size abstention.
"""

import pytest


def test_polarity_guard_negation_normality():
    """1. Legitimate non-normal statements (p < 0.05) must not trigger PREREQUISITE_LOGIC_INVERSION."""
    from backend.layer2_core.polarity_guard import PolarityGuard

    guard = PolarityGuard()
    text = "Data tidak berdistribusi normal karena nilai Sig. Kolmogorov-Smirnov sebesar 0,012 < 0,05."
    res = guard.check_prerequisite_inversion(text)
    assert res is None, f"Expected None for legitimate negation statement, got {res}"


def test_semantic_numeric_guard_year_prefix():
    """2. 'Pada 2021' must be classified as CITATION_YEAR and prevented from statistical linking."""
    from src.core.semantic_numeric_guard import classify_numeric_span

    sentence = "Pada 2021, nilai rata-rata DELAY sebesar 76,40."
    start_2021 = sentence.find("2021")
    end_2021 = start_2021 + len("2021")
    cls_2021 = classify_numeric_span(sentence, start_2021, end_2021, "2021")
    assert cls_2021 == "CITATION_YEAR", f"Expected CITATION_YEAR for 'Pada 2021', got {cls_2021}"

    start_val = sentence.find("76,40")
    end_val = start_val + len("76,40")
    cls_val = classify_numeric_span(sentence, start_val, end_val, "76,40")
    assert cls_val == "STAT_METRIC", f"Expected STAT_METRIC for '76,40', got {cls_val}"


def test_statcheck_anova_decision_flip():
    """3. ANOVA F(1, 50) = 2.10 with reported p = 0.005 must trigger DECISION_FLIP in CellLinker."""
    from backend.layer2_core.cell_linker import CellLinker

    linker = CellLinker()
    claim = {
        "claim_id": "C_TEST_ANOVA",
        "page": 1,
        "text": "Uji ANOVA menghasilkan F(1, 50) = 2,10 dengan p = 0,005.",
        "bbox": [50, 100, 300, 120]
    }
    findings = linker.link_claim_to_table(claim, [])
    assert len(findings) > 0, "Expected a finding for ANOVA statcheck error"
    flip_finding = next((f for f in findings if f.get("verdict") == "DECISION_FLIP"), None)
    assert flip_finding is not None, f"Expected DECISION_FLIP finding, got {[f.get('verdict') for f in findings]}"
    assert flip_finding["severity"] == "CRITICAL"


def test_pii_redactor_spss_decimal_and_nim():
    """4. PII redactor must keep long SPSS floats intact while redacting labeled NIM."""
    from backend.layer3_export.pii_redactor import PiiRedactor

    raw = "Mean = 1.487430741340253, NIM: 1512622045"
    redacted = PiiRedactor.redact_text(raw)
    assert "1.487430741340253" in redacted, f"SPSS floating decimal was corrupted: {redacted}"
    assert "1512622045" not in redacted, f"NIM was not redacted: {redacted}"
    assert "NIM: 1512[NIM-REDACTED]" in redacted


def test_cell_linker_mean_without_n_abstains():
    """5. CellLinker on mean claim without explicit N or table N column must abstain from GRIM."""
    from backend.layer2_core.cell_linker import CellLinker

    linker = CellLinker()
    claim = {
        "claim_id": "C_TEST_GRIM",
        "page": 1,
        "text": "Nilai rata-rata persepsi adalah 3,43.",
        "bbox": [50, 100, 300, 120]
    }
    table = {
        "table_id": "Tabel_1",
        "page": 1,
        "num_rows": 1,
        "num_cols": 2,
        "header_paths": ["Variabel", "Mean"],
        "rows": [
            [
                {"row_idx": 0, "col_idx": 0, "raw_val": "Persepsi", "num_val": None, "header_path": "Variabel", "row_label": "Persepsi"},
                {"row_idx": 0, "col_idx": 1, "raw_val": "3.43", "num_val": 3.43, "header_path": "Mean", "row_label": "Persepsi"}
            ]
        ]
    }
    findings = linker.link_claim_to_table(claim, [table], detected_total_n=None)
    grim_findings = [f for f in findings if f.get("verdict") == "GRIM_INCONSISTENCY"]
    assert len(grim_findings) == 0, f"Expected 0 GRIM false positives when N is absent, got {grim_findings}"
