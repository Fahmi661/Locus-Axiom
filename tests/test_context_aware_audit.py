"""
Test Suite: Pengujian Regresi Wajib Akurasi Kontekstual Audit LOCUS
Sesuai Instruksi Perbaikan:
- Ukuran Perusahaan (Min 12,55, Max 15,30, Mean 13,8688, Std. Dev 0,78033)
- Likuiditas (Min 0,17, Max 4,82, Mean 1,4831, Std. Dev 1,29417)
- Pencegahan Cross-Variable Row Swap
- Pencegahan False Positive Mean vs Min
- Pendeteksian True Negative (Kesalahan Asli)
- Dukungan Unicode En-dash (rata \u2013 rata) dan Typo Baris Tabel (Kepemilkan)
"""

import pytest
from src.core.quad_tuple_verifier import (
    extract_quad_tuples_from_sentence,
    verify_quad_tuple_against_table,
    match_variable_row_score,
    normalize_text_dashes,
    ClaimQuadTuple
)
from backend.layer2_core.cell_linker import match_sentence_to_row, CellLinker

TABLE_HEADERS = [
    "Descriptive Statistics",
    "Descriptive Statistics :: N",
    "Descriptive Statistics :: Minimum",
    "Descriptive Statistics :: Maximum",
    "Descriptive Statistics :: Mean",
    "Descriptive Statistics :: Std. Deviation"
]

TABLE_ROWS_DATA = [
    ["Ukuran Perusahaan", "96", "12,55", "15,30", "13,8688", ",78033"],
    ["Likuiditas", "96", ",17", "4,82", "1,4831", "1,29417"],
    ["Kepemilkan Publik", "96", ",46", ",93", ",6138", ",12152"]
]

ROW_LABELS = ["Ukuran Perusahaan", "Likuiditas", "Kepemilkan Publik"]


def test_ukuran_perusahaan_all_four_metrics_consistent():
    """Seluruh 4 metrik Ukuran Perusahaan wajib terverifikasi konsisten (VALID_EXACT)."""
    sentences = [
        ("MINIMUM", "Hasil analisis deskriptif pada variabel ukuran perusahaan memiliki nilai minimum sebesar 12,55."),
        ("MAXIMUM", "Nilai maksimum sebesar 15,30, artinya total aktiva tertinggi sebesar 15,30."),
        ("MEAN", "Nilai rata - rata sebesar 13,8688, artinya ukuran perusahaan relatif mendekati rata - rata."),
        ("STD_DEV", "Sedangkan standar deviasi sebesar 0,78033 lebih kecil dari nilai rata - rata.")
    ]
    for expected_stat, sent in sentences:
        quads = extract_quad_tuples_from_sentence(
            sent,
            candidate_table_variables=ROW_LABELS,
            default_variable="Ukuran Perusahaan"
        )
        assert len(quads) >= 1, f"Gagal mengekstrak quad dari: {sent}"
        primary_quad = [q for q in quads if q.stat_type == expected_stat][0]
        res = verify_quad_tuple_against_table(primary_quad, TABLE_HEADERS, TABLE_ROWS_DATA)
        assert res.status == "VALID_EXACT", f"Ekspektasi VALID_EXACT tapi dapat {res.status} untuk {expected_stat}"


def test_likuiditas_all_four_metrics_consistent():
    """Seluruh 4 metrik Likuiditas wajib terverifikasi konsisten (VALID_EXACT)."""
    sentences = [
        ("MINIMUM", "Hasil analisis deskriptif pada variabel likuiditas memiiki nilai minimum 0,17."),
        ("MAXIMUM", "Nilai maksimum sebesar 4,82, artinya kemampuan memenuhi kewajiban terbesar adalah 4,82."),
        ("MEAN", "Nilai rata - rata sebesar 1,4831, artinya perusahaan sampel relatif homogen."),
        ("STD_DEV", "Sedangkan standar deviasi sebesar 1,29417 lebih kecil dari rata - rata.")
    ]
    for expected_stat, sent in sentences:
        quads = extract_quad_tuples_from_sentence(
            sent,
            candidate_table_variables=ROW_LABELS,
            default_variable="Likuiditas"
        )
        assert len(quads) >= 1, f"Gagal mengekstrak quad dari: {sent}"
        primary_quad = [q for q in quads if q.stat_type == expected_stat][0]
        res = verify_quad_tuple_against_table(primary_quad, TABLE_HEADERS, TABLE_ROWS_DATA)
        assert res.status == "VALID_EXACT", f"Ekspektasi VALID_EXACT tapi dapat {res.status} untuk {expected_stat}"


def test_mean_different_from_minimum_not_flagged_as_contradiction():
    """Nilai Mean (13,8688) yang berbeda dari Minimum (12,55) tidak boleh dianggap salah kolom."""
    sent = "Nilai rata - rata sebesar 13,8688, artinya dekatnya selisih nilai minimum dengan nilai rata - rata."
    quads = extract_quad_tuples_from_sentence(
        sent,
        candidate_table_variables=ROW_LABELS,
        default_variable="Ukuran Perusahaan"
    )
    mean_quads = [q for q in quads if q.stat_type == "MEAN"]
    assert len(mean_quads) >= 1
    res = verify_quad_tuple_against_table(mean_quads[0], TABLE_HEADERS, TABLE_ROWS_DATA)
    assert res.status == "VALID_EXACT"


def test_cross_variable_isolation_sentence_matching():
    """
    Kalimat Likuiditas yang mengandung frasa penjelasan 'ukuran perusahaan' di anak kalimat
    TIDAK boleh tertukar baris dengan 'Ukuran Perusahaan'.
    """
    sent = "Nilai maksimum sebesar 4,82, artinya ukuran perusahaan yang mampu memenuhi kewajiban jangka pendek dengan asset lancarnya terbesar adalah 4,82."
    matched = match_sentence_to_row(
        sent,
        ROW_LABELS,
        discourse_var="Likuiditas",
        table_rows_data=TABLE_ROWS_DATA
    )
    assert matched == "Likuiditas", f"Harusnya terikat ke Likuiditas, tapi terikat ke: {matched}"


def test_typo_table_row_matching():
    """Teks 'kepemilikan publik' harus berhasil dicocokkan dengan baris tabel 'Kepemilkan Publik' (typo)."""
    sent = "Hasil analisis deskriptif pada variabel kepemilikan publik memiliki nilai minimum sebesar 0,46."
    matched = match_sentence_to_row(sent, ROW_LABELS)
    assert matched == "Kepemilkan Publik"

    quads = extract_quad_tuples_from_sentence(
        sent,
        candidate_table_variables=ROW_LABELS,
        default_variable=matched
    )
    min_quads = [q for q in quads if q.stat_type == "MINIMUM"]
    assert len(min_quads) >= 1
    res = verify_quad_tuple_against_table(min_quads[0], TABLE_HEADERS, TABLE_ROWS_DATA)
    assert res.status == "VALID_EXACT"


def test_unicode_en_dash_reduplication_handling():
    """Karakter en-dash Unicode (rata \u2013 rata) harus dinormalisasi dan diekstrak sebagai MEAN."""
    sent_with_en_dash = "Nilai rata \u2013 rata sebesar 13,8688 pada variabel ukuran perusahaan."
    quads = extract_quad_tuples_from_sentence(
        sent_with_en_dash,
        candidate_table_variables=ROW_LABELS,
        default_variable="Ukuran Perusahaan"
    )
    assert any(q.stat_type == "MEAN" and q.numeric_value == 13.8688 for q in quads)


def test_true_negative_actual_error_detected():
    """Uji Negatif: Angka yang benar-benar salah pada narasi harus tetap terdeteksi inkonsisten."""
    wrong_sent = "Hasil analisis deskriptif pada variabel ukuran perusahaan memiliki nilai minimum sebesar 99,99."
    quads = extract_quad_tuples_from_sentence(
        wrong_sent,
        candidate_table_variables=ROW_LABELS,
        default_variable="Ukuran Perusahaan"
    )
    assert len(quads) >= 1
    res = verify_quad_tuple_against_table(quads[0], TABLE_HEADERS, TABLE_ROWS_DATA)
    assert res.status == "VALUE_MISMATCH"
    assert res.table_cell_raw == "12,55"


def test_true_column_swap_detected():
    """Uji Negatif: Jika narasi benar-benar salah sebut kolom (menyebut Min padahal nilai Max), deteksi COLUMN_SWAP."""
    swap_sent = "Hasil analisis deskriptif pada variabel ukuran perusahaan memiliki nilai minimum sebesar 15,30."
    quads = extract_quad_tuples_from_sentence(
        swap_sent,
        candidate_table_variables=ROW_LABELS,
        default_variable="Ukuran Perusahaan"
    )
    assert len(quads) >= 1
    res = verify_quad_tuple_against_table(quads[0], TABLE_HEADERS, TABLE_ROWS_DATA)
    assert res.status == "COLUMN_SWAP_ERROR"
    assert "Maximum" in res.swapped_column_found
