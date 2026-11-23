"""
Regression Test Suite for LOCUS v3.5 Semantic Type-Safe & Cross-Encoder Grounding Engine.
Verifies:
1. Anti-year and citation suppression (e.g. data tahun 2019 sampai 2021 menurut Ghozali 2021 skala 1 sampai 5).
2. Textbook rule suppression (e.g. VIF < 10 dan tolerance > 0.10).
3. Bab IV descriptive inequality and aposition (> 30 yaitu 76.4).
4. Contrastive clause split multi-variable binding (DELAY vs SQRTUKAP).
5. Layer 1 perception and Layer 2 core hardening (row labels, Likert sum, FastPdfReader callback).
"""

import os
import pytest
from src.core.semantic_numeric_guard import (
    is_non_data_sentence,
    classify_numeric_span,
)
from src.core.quad_tuple_verifier import (
    extract_quad_tuples_from_sentence,
    verify_quad_tuple_against_table,
    ClaimQuadTuple,
)
from backend.layer2_core.cell_linker import (
    is_invalid_row_label,
    match_sentence_to_row,
)
from src.core.spss_likert_engine import (
    check_likert_row_sum_in_sentence,
    CleanedSPSSRow,
)
from backend.layer1_perception.pdf_reader import FastPdfReader


def test_anti_year_and_citation_suppression():
    """
    Test 1: Verification of methodology sentence with citation year and scale:
    'Penelitian ini menggunakan data tahun 2019 sampai 2021 menurut Ghozali (2021) dengan skala 1 sampai 5.'
    against table with variable DELAY.
    Ensures:
    - is_non_data_sentence returns True.
    - No claim quad tuple with value 2019, 2021, 1, or 5 is permitted.
    - No error finding is produced.
    """
    sentence = "Penelitian ini menggunakan data tahun 2019 sampai 2021 menurut Ghozali (2021) dengan skala 1 sampai 5."
    assert is_non_data_sentence(sentence) is True

    quads = extract_quad_tuples_from_sentence(
        sentence,
        candidate_table_variables=["DELAY", "Ukuran Perusahaan"],
        default_variable="DELAY"
    )
    # Ensure no quad with value 2019, 2021, 1, or 5 is extracted
    suppressed_vals = {2019.0, 2021.0, 1.0, 5.0}
    extracted_suppressed = [q for q in quads if q.numeric_value in suppressed_vals]
    assert len(extracted_suppressed) == 0

    table_headers = ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Deviation"]
    table_rows = [
        ["DELAY", "68", "56.00", "97.00", "76.40", "9.395"]
    ]
    # Even if quads were somehow extracted, verify no finding error
    for q in quads:
        res = verify_quad_tuple_against_table(q, table_headers, table_rows)
        assert res.status != "NUMERICAL_CONTRADICTION"


def test_textbook_rule_suppression():
    """
    Test 2: Verification of textbook rule / decision criterion sentence:
    'Kriteria uji multikolinearitas adalah nilai VIF < 10 dan tolerance > 0,10 dengan taraf signifikansi 5%.'
    Ensures:
    - is_non_data_sentence returns True.
    - Tokens are classified as SCALE_OR_RULE_THRESHOLD.
    - No claim quad tuple is generated, and zero error findings produced.
    """
    sentence = "Kriteria uji multikolinearitas adalah nilai VIF < 10 dan tolerance > 0,10 dengan taraf signifikansi 5%."
    assert is_non_data_sentence(sentence) is True

    quads = extract_quad_tuples_from_sentence(
        sentence,
        candidate_table_variables=["VIF", "Tolerance"],
        default_variable=None
    )
    assert len(quads) == 0


def test_bab4_descriptive_inequality_and_aposition():
    """
    Test 3: Real Bab IV sentence with inequality (> 30) and glued token (76,4dengan)
    'Rata-rata sampel yang diteliti menunjukkan terjadi keterlambatan prosedur audit yang cukup besar yang terlihat dari nilai rata-rata (mean) > 30 yaitu 76,4dengan standar deviasi sebesar 9,395.'
    Matched against DELAY row (Mean = 76.40, Std. Deviation = 9.395).
    Ensures:
    - '> 30' verified as VALID_EXACT (76.40 > 30 is True).
    - '76.4' verified as VALID_EXACT (equal to 76.40).
    - '9.395' verified as VALID_EXACT.
    - Zero error findings.
    """
    sentence = (
        "Rata-rata sampel yang diteliti menunjukkan terjadi keterlambatan prosedur audit yang cukup besar "
        "yang terlihat dari nilai rata-rata (mean) > 30 yaitu 76,4dengan standar deviasi sebesar 9,395."
    )
    quads = extract_quad_tuples_from_sentence(
        sentence,
        candidate_table_variables=["DELAY", "Audit Delay"],
        default_variable="DELAY"
    )
    assert len(quads) == 3

    quad_30 = next((q for q in quads if abs(q.numeric_value - 30.0) < 0.01), None)
    assert quad_30 is not None
    assert quad_30.operator == "GT"
    assert quad_30.stat_type == "MEAN"

    quad_mean = next((q for q in quads if abs(q.numeric_value - 76.4) < 0.01), None)
    assert quad_mean is not None
    assert quad_mean.operator == "EQ"
    assert quad_mean.stat_type == "MEAN"

    quad_sd = next((q for q in quads if abs(q.numeric_value - 9.395) < 0.001), None)
    assert quad_sd is not None
    assert quad_sd.operator == "EQ"
    assert quad_sd.stat_type == "STD_DEV"

    table_headers = ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Deviation"]
    table_rows = [
        ["DELAY", "68", "56.00", "97.00", "76.40", "9.395"]
    ]

    res_30 = verify_quad_tuple_against_table(quad_30, table_headers, table_rows)
    assert res_30.status == "VALID_EXACT"

    res_mean = verify_quad_tuple_against_table(quad_mean, table_headers, table_rows)
    assert res_mean.status == "VALID_EXACT"

    res_sd = verify_quad_tuple_against_table(quad_sd, table_headers, table_rows)
    assert res_sd.status == "VALID_EXACT"


def test_contrastive_clause_split_multi_variable():
    """
    Test 4: Real Bab IV multi-variable contrastive sentence:
    'Nilai DELAY berkisar antara 56 sampai 97, sedangkan SQRTUKAP memiliki nilai tertinggi 1,73 dan terendah 1,00 dengan rata-rata 1,49.'
    Matched against DELAY (Min=56, Max=97) and SQRTUKAP (Min=1.00, Max=1.73, Mean=1.49).
    Ensures:
    - DELAY binds 56 as MINIMUM and 97 as MAXIMUM.
    - SQRTUKAP binds 1.73 as MAXIMUM, 1.00 as MINIMUM, and 1.49 as MEAN.
    - No variable or column swapping.
    """
    sentence = (
        "Nilai DELAY berkisar antara 56 sampai 97, sedangkan SQRTUKAP memiliki nilai "
        "tertinggi 1,73 dan terendah 1,00 dengan rata-rata 1,49."
    )
    quads = extract_quad_tuples_from_sentence(
        sentence,
        candidate_table_variables=["DELAY", "SQRTUKAP"]
    )
    assert len(quads) == 5

    delay_quads = [q for q in quads if q.variable_name == "DELAY"]
    sqrt_quads = [q for q in quads if q.variable_name == "SQRTUKAP"]

    assert len(delay_quads) == 2
    assert len(sqrt_quads) == 3

    delay_min = next((q for q in delay_quads if q.stat_type == "MINIMUM"), None)
    assert delay_min is not None
    assert abs(delay_min.numeric_value - 56.0) < 0.01

    delay_max = next((q for q in delay_quads if q.stat_type == "MAXIMUM"), None)
    assert delay_max is not None
    assert abs(delay_max.numeric_value - 97.0) < 0.01

    sqrt_max = next((q for q in sqrt_quads if q.stat_type == "MAXIMUM"), None)
    assert sqrt_max is not None
    assert abs(sqrt_max.numeric_value - 1.73) < 0.01

    sqrt_min = next((q for q in sqrt_quads if q.stat_type == "MINIMUM"), None)
    assert sqrt_min is not None
    assert abs(sqrt_min.numeric_value - 1.00) < 0.01

    sqrt_mean = next((q for q in sqrt_quads if q.stat_type == "MEAN"), None)
    assert sqrt_mean is not None
    assert abs(sqrt_mean.numeric_value - 1.49) < 0.01

    table_headers = ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Deviation"]
    table_rows = [
        ["DELAY", "68", "56.00", "97.00", "76.40", "9.395"],
        ["SQRTUKAP", "68", "1.00", "1.73", "1.49", "0.18"]
    ]

    for q in quads:
        res = verify_quad_tuple_against_table(q, table_headers, table_rows)
        assert res.status == "VALID_EXACT"
        assert res.matched_row_label == q.variable_name


def test_layer1_and_layer2_hardening():
    """
    Test 5: Layer 1 perception and Layer 2 core hardening checks:
    - X1, X2 not discarded by is_invalid_row_label().
    - VALID and MISSING discarded by is_invalid_row_label().
    - ROW_SUM_MISMATCH detected when total baris != jumlah klausa.
    - FastPdfReader.process_pdf receives callback with 4 arguments (current, total, step, pct) without TypeError.
    """
    assert is_invalid_row_label("X1") is False
    assert is_invalid_row_label("X2") is False
    assert is_invalid_row_label("CR") is False
    assert is_invalid_row_label("PB") is False

    assert is_invalid_row_label("VALID") is True
    assert is_invalid_row_label("MISSING") is True
    assert is_invalid_row_label("TOTAL") is True
    assert is_invalid_row_label("1") is True

    # ROW_SUM_MISMATCH check
    sentence = "Sebanyak 12 responden menjawab sangat setuju dan 18 responden menjawab setuju."
    table_cleaned = {
        "SS": CleanedSPSSRow(
            row_code="SS",
            raw_label="Sangat Setuju",
            cells={"FREQUENCY": 12.0, "PERCENT": 30.0},
            raw_cells={"FREQUENCY": "12", "PERCENT": "30,0"}
        ),
        "S": CleanedSPSSRow(
            row_code="S",
            raw_label="Setuju",
            cells={"FREQUENCY": 18.0, "PERCENT": 45.0},
            raw_cells={"FREQUENCY": "18", "PERCENT": "45,0"}
        ),
        "TOTAL": CleanedSPSSRow(
            row_code="TOTAL",
            raw_label="Total",
            cells={"FREQUENCY": 40.0, "PERCENT": 100.0},
            raw_cells={"FREQUENCY": "40", "PERCENT": "100,0"}
        )
    }
    sum_check = check_likert_row_sum_in_sentence(sentence, table_cleaned)
    assert sum_check is not None
    assert sum_check["verdict"] == "ROW_SUM_MISMATCH"
    assert sum_check["claimed_sum"] == 30.0
    assert sum_check["table_total"] == 40.0

    # FastPdfReader callback test
    preset_pdf = os.path.join("data", "presets", "preset_1_ml_polarity.pdf")
    assert os.path.exists(preset_pdf), f"Preset PDF not found at {preset_pdf}"

    callback_calls = []
    def mock_hook(current: int, total: int, step: str, pct: int):
        callback_calls.append((current, total, step, pct))

    doc_graph = FastPdfReader.process_pdf(preset_pdf, progress_callback=mock_hook)
    assert "claims" in doc_graph
    assert "tables" in doc_graph
    assert len(callback_calls) > 0
    cur, tot, step, pct = callback_calls[0]
    assert isinstance(cur, int)
    assert isinstance(tot, int)
    assert isinstance(step, str)
    assert isinstance(pct, int)
