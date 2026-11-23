# -*- coding: utf-8 -*-
"""
Test Suite: LOCUS v3.6 High-Precision Detection Overhaul
Verifies the 7 architectural fixes for table detection, SPSS frequency alignment,
variable prefix stripping, inline Z-formula verification, Likert sum splitting,
and 100% offline frontend asset hygiene.
"""

import os
import re
import pytest
from src.core.quad_tuple_verifier import normalize_variable_stem
from src.core.spss_likert_engine import (
    normalize_table_id,
    route_claim_to_exact_table,
    parse_spss_frequency_table,
    check_likert_row_sum_in_sentence
)
from backend.layer1_perception.table_geometry import (
    TableGeometryExtractor,
    has_sub_header
)
from backend.layer2_core.cell_linker import (
    CellLinker,
    match_sentence_to_row
)
from backend.layer2_core.stat_solvers import FormulaEvalSolver


def test_1_caption_regex_and_multi_table_routing():
    # 1. Caption normalization with spaces after punctuation
    assert normalize_table_id("Tabel IV. 7") == "4.7"
    assert normalize_table_id("tabel IV.7") == "4.7"
    assert normalize_table_id("Tabel 4. 7") == "4.7"
    assert normalize_table_id("Tabel 4-7") == "4.7"

    # 2. Multi-table routing: never fallback to wrong table when explicit ID is requested
    tables = [
        {
            "table_id": "Tabel 4.6",
            "normalized_id": "4.6",
            "bbox": [50, 100, 500, 200]
        }
    ]
    # Sentence explicitly mentions Tabel IV.7 which is NOT in tables -> must return None (abstain)
    routed = route_claim_to_exact_table("Menurut tabel IV.7 hasil analisis deskriptif...", 1, 300.0, tables)
    assert routed is None

    # When exact table exists, it routes accurately
    tables.append({
        "table_id": "Tabel IV. 7",
        "normalized_id": "4.7",
        "bbox": [50, 220, 500, 320]
    })
    routed_exact = route_claim_to_exact_table("Menurut tabel IV.7 hasil analisis deskriptif...", 1, 350.0, tables)
    assert routed_exact is not None
    assert routed_exact["normalized_id"] == "4.7"


def test_2_spss_frequency_table_right_aligned_binding():
    # SPSS 6-column frequency table with Valid stub
    headers = ["", "", "Frequency", "Percent", "Valid Percent", "Cumulative Percent"]
    rows = [
        ["Valid", "STS", "5", "5.0", "5.0", "5.0"],
        ["", "TS", "15", "15.0", "15.0", "20.0"],
        ["", "Total", "100", "100.0", "100.0", ""]
    ]

    parsed = parse_spss_frequency_table(headers, rows)
    assert "STS" in parsed
    assert parsed["STS"].cells["FREQUENCY"] == 5.0
    assert parsed["STS"].cells["PERCENT"] == 5.0
    assert parsed["STS"].cells["VALID_PERCENT"] == 5.0
    assert parsed["STS"].cells["CUMULATIVE_PERCENT"] == 5.0

    assert "TS" in parsed
    assert parsed["TS"].cells["FREQUENCY"] == 15.0
    assert parsed["TS"].cells["PERCENT"] == 15.0
    assert parsed["TS"].cells["VALID_PERCENT"] == 15.0
    assert parsed["TS"].cells["CUMULATIVE_PERCENT"] == 20.0


def test_3_variable_prefix_stripping_and_parenthetical_alias():
    # Prefix stripping
    assert normalize_variable_stem("X2_SIZE") == "size"
    assert normalize_variable_stem("Y_ROE") == "roe"
    assert normalize_variable_stem("X1_DER") == "der"
    assert normalize_variable_stem("Z_PG") == "pg"
    assert normalize_variable_stem("SQRTUKAP") == "ukap"

    # Parenthetical alias sentence matching
    sentence = "standar deviasi tertinggi adalah ukuran perusahaan (size) yaitu sebesar 5,70214"
    valid_labels = ["X1_DER", "X2_SIZE", "Y_ROE"]
    matched = match_sentence_to_row(sentence, valid_labels)
    assert matched == "X2_SIZE"


def test_4_has_sub_header_preserves_first_data_row():
    # Row with numeric data like "Ketepatan Waktu | 96 | ,00 | 1,00"
    data_row = ["Ketepatan Waktu", "96", ",00", "1,00"]
    # Should NOT be classified as sub_header
    assert has_sub_header(data_row) is False

    # Actual sub-header without numbers
    sub_header_row = ["No", "Nama Variabel", "Mean", "Std. Deviation"]
    assert has_sub_header(sub_header_row) is True


def test_5_z_formula_verification_and_narrative_contradiction():
    # Exact math: stat_val = -0.420, N = 68 -> SE = sqrt(24/68) = 0.5940885, Z = 0.707
    # Case A: Formula says 0.71, no contradiction -> PASS (0 error)
    res_pass = FormulaEvalSolver.audit_z_formula(
        metric_name="kurtosis",
        stat_val=-0.420,
        n_sample=68,
        reported_z=0.71,
        narrative_claimed_z=None
    )
    assert res_pass["verdict"] == "PASS"

    # Case B: Formula says 0.71, but narrative text claims 1.05 -> INLINE_FORMULA_NARRATIVE_CONTRADICTION
    res_contra = FormulaEvalSolver.audit_z_formula(
        metric_name="kurtosis",
        stat_val=-0.420,
        n_sample=68,
        reported_z=0.71,
        narrative_claimed_z=1.05
    )
    assert res_contra["verdict"] == "INLINE_FORMULA_NARRATIVE_CONTRADICTION"

    # Case C: End-to-end CellLinker integration check
    linker = CellLinker()
    claim_formula = {
        "claim_id": "CF_1",
        "page": 1,
        "text": "Zkurtosis = 0,71",
        "bbox": [72, 100, 500, 120]
    }
    all_c_pass = [
        {"claim_id": "CF_1", "page": 1, "text": "Zkurtosis = 0,71"},
        {"claim_id": "CF_2", "page": 1, "text": "Zkurtosis menunjukkan 0.71 menandakan data berdistribusi normal."}
    ]
    findings_pass = linker.link_claim_to_table(claim_formula, [], all_claims=all_c_pass)
    assert len(findings_pass) == 0  # 0 FP

    all_c_contra = [
        {"claim_id": "CF_1", "page": 1, "text": "Zkurtosis = 0,71"},
        {"claim_id": "CF_2", "page": 1, "text": "Hasil perhitungan Zkurtosis menunjukkan 1.05 menandakan lebih kecil dari Z tabel."}
    ]
    findings_contra = linker.link_claim_to_table(claim_formula, [], all_claims=all_c_contra)
    assert len(findings_contra) == 1
    f0 = findings_contra[0]
    assert f0["verdict"] == "INLINE_FORMULA_NARRATIVE_CONTRADICTION"
    assert "1.05" in f0["diff_details"]["claimed_val"]
    assert "0.71" in f0["diff_details"]["table_val"]
    assert "0.71" in f0["diff_details"]["plain_explanation"]
    assert "1.05" in f0["diff_details"]["plain_explanation"]


def test_6_likert_row_sum_selective_mention():
    headers = ["", "", "Frequency", "Percent", "Valid Percent", "Cumulative Percent"]
    rows = [
        ["Valid", "STS", "2", "2.0", "2.0", "2.0"],
        ["", "TS", "5", "5.0", "5.0", "7.0"],
        ["", "N", "5", "5.0", "5.0", "12.0"],
        ["", "S", "48", "48.0", "48.0", "60.0"],
        ["", "SS", "40", "40.0", "40.0", "100.0"],
        ["", "Total", "100", "100.0", "100.0", ""]
    ]
    table_cleaned = parse_spss_frequency_table(headers, rows)

    # Sentence only mentions the 2 majority categories (48 + 40 = 88 < 100) -> NOT a row sum mismatch
    sent_subset = "Sebanyak 48 responden menyatakan setuju dan 40 responden menyatakan sangat setuju."
    mismatch_subset = check_likert_row_sum_in_sentence(sent_subset, table_cleaned)
    assert mismatch_subset is None

    # Sentence claims more than total sample (60 + 50 = 110 > 100) -> MUST flag ROW_SUM_MISMATCH
    sent_exceeded = "Sebanyak 60 responden menyatakan setuju dan 50 responden menyatakan sangat setuju."
    mismatch_exceeded = check_likert_row_sum_in_sentence(sent_exceeded, table_cleaned)
    assert mismatch_exceeded is not None
    assert mismatch_exceeded["verdict"] == "ROW_SUM_MISMATCH"
    assert mismatch_exceeded["claimed_sum"] == 110.0


def test_7_zero_external_links_in_frontend():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_files = [
        os.path.join(base_dir, "frontend", "index.html"),
        os.path.join(base_dir, "frontend", "studio.html")
    ]

    for html_path in html_files:
        assert os.path.exists(html_path), f"File {html_path} must exist"
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for any external URLs in script src or link href
        script_links = re.findall(r'<script[^>]+src=["\'](https?://[^"\']+)["\']', content, re.IGNORECASE)
        css_links = re.findall(r'<link[^>]+href=["\'](https?://[^"\']+)["\']', content, re.IGNORECASE)

        assert len(script_links) == 0, f"Found external scripts in {html_path}: {script_links}"
        assert len(css_links) == 0, f"Found external stylesheets/links in {html_path}: {css_links}"
