"""
Regression Test Suite for LOCUS CPU-Ready Architecture Fixes.
Verifies:
1. Glued decimal token separation and comparative inequality & apositive handling.
2. Multi-number superlative/comparative binding without explicit 'nilai' noun.
3. 2-character valid variable labels (X1, X2, CR, PB) and rejection of VALID/MISSING.
4. SPSS Likert row sum mismatch detection.
5. FastPdfReader progress_callback signature synchronization.
"""

import os
import pytest
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


def test_glued_number_and_comparative_operator():
    """
    Test 1: Glued token (76,4dengan) separated properly, inequality operator (GT) detected,
    and apositive ('yaitu') does not sever MEAN binding.
    """
    sentence = (
        "Rata-rata sampel yang diteliti menunjukkan keterlambatan audit delay > 30 "
        "yaitu 76,4dengan standar deviasi 18,2."
    )
    quads = extract_quad_tuples_from_sentence(
        sentence,
        candidate_table_variables=["Audit Delay", "DELAY"],
        default_variable="Audit Delay"
    )

    assert len(quads) >= 2
    
    # Check operator for 30
    quad_30 = next((q for q in quads if abs(q.numeric_value - 30.0) < 0.01), None)
    assert quad_30 is not None
    assert quad_30.operator == "GT"

    # Check 76.4 is extracted and bound to MEAN with EQ operator
    quad_mean = next((q for q in quads if abs(q.numeric_value - 76.4) < 0.01), None)
    assert quad_mean is not None
    assert quad_mean.stat_type == "MEAN"
    assert quad_mean.operator == "EQ"

    # Verify inequality against table where MEAN is 76.40
    table_headers = ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Deviation"]
    table_rows = [
        ["Audit Delay", "68", "30.00", "150.00", "76.40", "18.20"]
    ]

    res_30 = verify_quad_tuple_against_table(quad_30, table_headers, table_rows)
    assert res_30.status == "VALID_EXACT"

    res_mean = verify_quad_tuple_against_table(quad_mean, table_headers, table_rows)
    assert res_mean.status == "VALID_EXACT"


def test_superlative_comparative_without_explicit_nilai():
    """
    Test 2: Academic sentence with superlative and comparative without explicit 'nilai' noun.
    'menunjukkan tingkat tertinggi pada 3,46 dan terendah 1 dengan rata-rata 2,67'
    """
    sentence = "Variabel CR menunjukkan tingkat tertinggi pada 3,46 dan terendah 1 dengan rata-rata 2,67."
    quads = extract_quad_tuples_from_sentence(
        sentence,
        candidate_table_variables=["CR", "Current Ratio"],
        default_variable="CR"
    )

    assert len(quads) == 3

    quad_max = next((q for q in quads if abs(q.numeric_value - 3.46) < 0.01), None)
    assert quad_max is not None
    assert quad_max.stat_type == "MAXIMUM"
    assert quad_max.variable_name == "CR"

    quad_min = next((q for q in quads if abs(q.numeric_value - 1.0) < 0.01), None)
    assert quad_min is not None
    assert quad_min.stat_type == "MINIMUM"
    assert quad_min.variable_name == "CR"

    quad_mean = next((q for q in quads if abs(q.numeric_value - 2.67) < 0.01), None)
    assert quad_mean is not None
    assert quad_mean.stat_type == "MEAN"
    assert quad_mean.variable_name == "CR"

    # Verify against table
    table_headers = ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Deviation"]
    table_rows = [
        ["CR", "68", "1.00", "3.46", "2.67", "0.55"]
    ]
    for q in (quad_max, quad_min, quad_mean):
        res = verify_quad_tuple_against_table(q, table_headers, table_rows)
        assert res.status in ("VALID_EXACT", "VALID_ROUNDED")


def test_two_character_variable_labels():
    """
    Test 3: Valid 2-character variable labels are allowed (not rejected),
    while pure numbers, 1-char, VALID, and MISSING are rejected.
    """
    # 2-char valid variables
    assert is_invalid_row_label("X1") is False
    assert is_invalid_row_label("X2") is False
    assert is_invalid_row_label("CR") is False
    assert is_invalid_row_label("PB") is False
    assert is_invalid_row_label("TA") is False

    # Invalid row labels
    assert is_invalid_row_label("VALID") is True
    assert is_invalid_row_label("MISSING") is True
    assert is_invalid_row_label("TOTAL") is True
    assert is_invalid_row_label("1") is True
    assert is_invalid_row_label("X") is True

    # Matching sentence to 2-char row
    sent = "Hasil uji statistik deskriptif pada variabel X1 menunjukkan rata-rata sebesar 3,5."
    matched = match_sentence_to_row(sent, ["X1", "X2", "Y1"])
    assert matched == "X1"


def test_likert_row_sum_mismatch():
    """
    Test 4: check_likert_row_sum_in_sentence detects discrepancy between
    narrative frequency sum and table Total Frequency.
    """
    sentence = (
        "Sebanyak 15 responden menyatakan sangat setuju dan 20 responden menyatakan setuju."
    )
    # Claimed sum = 15 + 20 = 35 responden
    # Table total frequency = 40 responden
    table_cleaned = {
        "SS": CleanedSPSSRow(
            row_code="SS",
            raw_label="Sangat Setuju",
            cells={"FREQUENCY": 15.0, "PERCENT": 37.5},
            raw_cells={"FREQUENCY": "15", "PERCENT": "37,5"}
        ),
        "S": CleanedSPSSRow(
            row_code="S",
            raw_label="Setuju",
            cells={"FREQUENCY": 20.0, "PERCENT": 50.0},
            raw_cells={"FREQUENCY": "20", "PERCENT": "50,0"}
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
    assert sum_check["claimed_sum"] == 35.0
    assert sum_check["table_total"] == 40.0


def test_fast_pdf_reader_progress_callback():
    """
    Test 5: FastPdfReader.process_pdf with progress_callback matching
    signature (current_page, total_pages, step_name, pct) without TypeError.
    """
    preset_pdf = os.path.join("data", "presets", "preset_1_ml_polarity.pdf")
    assert os.path.exists(preset_pdf), f"Preset PDF not found at {preset_pdf}"

    callback_calls = []

    def mock_progress(current_page: int, total_pages: int, step_name: str, pct: int):
        callback_calls.append({
            "current_page": current_page,
            "total_pages": total_pages,
            "step_name": step_name,
            "pct": pct
        })

    doc_graph = FastPdfReader.process_pdf(
        preset_pdf,
        progress_callback=mock_progress
    )

    assert "claims" in doc_graph
    assert "tables" in doc_graph
    assert len(callback_calls) > 0
    # Verify signature types
    first_call = callback_calls[0]
    assert isinstance(first_call["current_page"], int)
    assert isinstance(first_call["total_pages"], int)
    assert isinstance(first_call["step_name"], str)
    assert isinstance(first_call["pct"], int)
