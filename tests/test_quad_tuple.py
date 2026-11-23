"""
Unit Tests for LOCUS v3.2 Quad-Tuple Grounding and Rounding Tolerance Engine.
Ensures zero cross-column collisions, exact statistical type binding,
and robust rounding/truncation/swap diagnostics.
"""

import pytest
from src.core.quad_tuple_verifier import (
    extract_quad_tuples_from_sentence,
    verify_quad_tuple_against_table,
    parse_academic_number,
    check_rounding_and_truncation,
    match_variable_row_score
)


def test_spss_sentence_with_5_numbers():
    """
    Test 1: Kalimat deskriptif SPSS dengan 5 angka sekaligus
    (N, Minimum, Maximum, Mean, Std. Deviation) dalam 1 kalimat.
    """
    sentence = (
        "Berdasarkan Tabel 4.2, variabel Audit Delay dengan jumlah sampel sebanyak 68 perusahaan "
        "memiliki nilai terendah sebesar 42,00, nilai tertinggi sebesar 151,00, nilai rata-rata (mean) sebesar 84,32, "
        "dan standar deviasi sebesar 21,454."
    )
    table_headers = ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Deviation"]
    table_rows = [
        ["Audit Delay", "68", "42.00", "151.00", "84.32", "21.454"]
    ]

    quads = extract_quad_tuples_from_sentence(sentence, candidate_table_variables=["Audit Delay"])
    assert len(quads) == 5

    stat_types = [q.stat_type for q in quads]
    assert "N" in stat_types
    assert "MINIMUM" in stat_types
    assert "MAXIMUM" in stat_types
    assert "MEAN" in stat_types
    assert "STD_DEV" in stat_types

    # Verify each against table
    for q in quads:
        res = verify_quad_tuple_against_table(q, table_headers, table_rows)
        assert res.status in ("VALID_EXACT", "VALID_ROUNDED")
        assert res.matched_row_label == "Audit Delay"


def test_rounding_and_truncation_cases():
    """
    Test 2: Kasus pembulatan .425243033944620 -> 0,43 (VALID_ROUNDED) dan 0,42 (TRUNCATION_WARNING).
    """
    table_headers = ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Deviation"]
    table_rows = [
        ["Ukuran KAP", "68", "0.00", "1.00", ".425243033944620", ".498"]
    ]

    # Sub-case A: 0,43 (Proper Rounding)
    sent_rounded = "Variabel Ukuran KAP memiliki nilai rata-rata sebesar 0,43."
    quads_rounded = extract_quad_tuples_from_sentence(sent_rounded, ["Ukuran KAP"])
    assert len(quads_rounded) == 1
    res_a = verify_quad_tuple_against_table(quads_rounded[0], table_headers, table_rows)
    assert res_a.status == "VALID_ROUNDED"

    # Sub-case B: 0,42 (SPSS Truncation)
    sent_trunc = "Variabel Ukuran KAP memiliki nilai rata-rata sebesar 0,42."
    quads_trunc = extract_quad_tuples_from_sentence(sent_trunc, ["Ukuran KAP"])
    assert len(quads_trunc) == 1
    res_b = verify_quad_tuple_against_table(quads_trunc[0], table_headers, table_rows)
    assert res_b.status == "TRUNCATION_WARNING"


def test_column_swap_error_detection():
    """
    Test 3: Kasus tertukar kolom (Mean ditulis menggunakan angka Minimum -> COLUMN_SWAP_ERROR).
    """
    table_headers = ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Deviation"]
    table_rows = [
        ["Profitabilitas", "68", "1.00", "5.00", "3.45", "0.82"]
    ]

    # Penulis salah klaim: menyebut rata-rata adalah 1,00 (padahal 1,00 adalah Minimum)
    sent_swap = "Variabel Profitabilitas memiliki nilai rata-rata sebesar 1,00."
    quads = extract_quad_tuples_from_sentence(sent_swap, ["Profitabilitas"])
    assert len(quads) == 1
    assert quads[0].stat_type == "MEAN"
    assert quads[0].numeric_value == 1.0

    res = verify_quad_tuple_against_table(quads[0], table_headers, table_rows)
    assert res.status == "COLUMN_SWAP_ERROR"
    assert res.swapped_column_found == "Minimum"


def test_morphological_variable_transformation_alias():
    """
    Test 4: Kasus variabel transformasi Ukuran KAP (UKKAP) di teks vs SQRTKAP di tabel.
    """
    table_headers = ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Deviation"]
    table_rows = [
        ["SQRTKAP", "68", "0.00", "1.00", "0.43", "0.50"]
    ]

    sent_alias = "Melihat item Ukuran KAP (UKKAP), variabel ini memiliki nilai rata-rata sebesar 0,43."
    quads = extract_quad_tuples_from_sentence(sent_alias, ["SQRTKAP"])
    assert len(quads) == 1
    assert quads[0].variable_name == "SQRTKAP"

    res = verify_quad_tuple_against_table(quads[0], table_headers, table_rows)
    assert res.status in ("VALID_EXACT", "VALID_ROUNDED")
    assert res.matched_row_label == "SQRTKAP"


def test_inverted_passive_sentence_hybrid():
    """
    Test 5: Kasus kalimat pasif / inversi (angka di depan, jenis statistik di belakang)
    yang ditangani oleh Hybrid Fallback.
    Contoh: 'Sebesar 84,32 tercatat sebagai nilai rata-rata pada variabel Audit Delay.'
    """
    table_headers = ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Deviation"]
    table_rows = [
        ["Audit Delay", "68", "42.00", "151.00", "84.32", "21.454"]
    ]

    sent_inverted = "Sebesar 84,32 tercatat sebagai nilai rata-rata pada variabel Audit Delay."
    quads = extract_quad_tuples_from_sentence(sent_inverted, ["Audit Delay"])
    assert len(quads) >= 1
    assert quads[0].stat_type == "MEAN"
    assert quads[0].numeric_value == 84.32
    assert quads[0].variable_name == "Audit Delay"

    res = verify_quad_tuple_against_table(quads[0], table_headers, table_rows)
    assert res.status in ("VALID_EXACT", "VALID_ROUNDED")
    assert res.matched_row_label == "Audit Delay"


def test_comparative_inequality_and_apositive_delay():
    """
    Test 6: Kalimat komparatif pertidaksamaan (> 30) dan apositif (yaitu 76,4).
    'Rata-rata sampel yang diteliti menunjukkan terjadi keterlambatan prosedur audit yang cukup besar yang terlihat dari nilai rata-rata (mean) > 30 yaitu 76,4 dengan standar deviasi sebesar 9,395.'
    terhadap tabel DELAY (Mean = 76.40, Std. Deviation = 9.395).
    Hasilnya harus 0 error (100% VALID).
    """
    sentence = (
        "Rata-rata sampel yang diteliti menunjukkan terjadi keterlambatan prosedur audit yang cukup besar "
        "yang terlihat dari nilai rata-rata (mean) > 30 yaitu 76,4 dengan standar deviasi sebesar 9,395."
    )
    table_headers = ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Deviation"]
    table_rows = [
        ["DELAY", "68", "14.00", "151.00", "76.40", "9.395"]
    ]

    quads = extract_quad_tuples_from_sentence(
        sentence,
        candidate_table_variables=["DELAY"],
        default_variable="DELAY"
    )
    assert len(quads) >= 2

    # Verifikasi setiap quad terhadap tabel
    valid_count = 0
    for q in quads:
        res = verify_quad_tuple_against_table(q, table_headers, table_rows)
        if res.status in ("VALID_EXACT", "VALID_ROUNDED"):
            valid_count += 1

    assert valid_count >= 2

    # Verifikasi dengan CellLinker end-to-end
    from backend.layer2_core.cell_linker import CellLinker
    linker = CellLinker()
    doc_graph = {
        "document_id": "TEST-DELAY",
        "claims": [{
            "claim_id": "C_TEST_DELAY",
            "page": 1,
            "text": sentence,
            "claim_y_top": 200.0,
            "bbox": [50, 190, 500, 215],
            "boxes": [[50, 190, 500, 215]]
        }],
        "tables": [{
            "table_id": "Tabel_4_1",
            "normalized_id": "4.1",
            "caption": "Descriptive Statistics",
            "page": 1,
            "bbox": [50, 50, 500, 150],
            "header_paths": table_headers,
            "rows": [
                [
                    {"row_label": "DELAY", "raw_val": "DELAY"},
                    {"raw_val": "68", "num_val": 68.0},
                    {"raw_val": "14.00", "num_val": 14.0},
                    {"raw_val": "151.00", "num_val": 151.0},
                    {"raw_val": "76.40", "num_val": 76.40},
                    {"raw_val": "9.395", "num_val": 9.395}
                ]
            ]
        }],
        "page_dimensions": {1: [595.0, 842.0, 0.0, 0.0]}
    }
    audit_res = linker.audit_document(doc_graph)
    # Zero error / contradictions detected
    error_findings = [f for f in audit_res.get("findings", []) if f.get("verdict") != "PASS_EXACT_MATCH"]
    assert len(error_findings) == 0
    assert audit_res["summary_counts"]["contradiction_or_flip_count"] == 0
