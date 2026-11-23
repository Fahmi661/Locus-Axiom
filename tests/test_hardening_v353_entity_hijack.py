"""
Test Suite: Hardening v3.5.3 - Entity Hijacking & False Positive Prevention
Pengujian Regresi Wajib:
1. Normalisasi desimal SPSS tanpa nol di depan (,17, -,45, ,00, .17, -.45).
2. Heading sub-bab 4.2.1.4 Likuiditas + kalimat pertama -> tertaut ke Likuiditas, 0 fatal.
3. Kalimat kedua di bawah heading sama -> tertaut ke Likuiditas via anchor, 0 fatal.
4. Tes negatif -> klaim 9,99 di bawah Likuiditas tertaut ke Likuiditas dan fatal (bukan Ukuran Perusahaan).
"""

import pytest
from src.core.quad_tuple_verifier import (
    parse_academic_number,
    extract_quad_tuples_from_sentence,
    verify_quad_tuple_against_table
)
from backend.layer2_core.cell_linker import CellLinker, match_sentence_to_row

# Simulasi Tabel 4.1 nyata
TABLE_HEADERS = [
    "Variabel",
    "N",
    "Minimum",
    "Maximum",
    "Mean",
    "Std. Deviation"
]

TABLE_ROWS_RAW = [
    ["Ketepatan Waktu", "96", "1", "1", "1,00", ",000"],
    ["Umur Perusahaan", "96", "4", "50", "22,50", "11,200"],
    ["Ukuran Perusahaan", "96", "12,55", "15,30", "13,8688", ",78033"],
    ["Likuiditas", "96", ",17", "4,82", "1,4831", "1,29417"],
    ["Profitabilitas", "96", "-,45", ",36", ",0850", ",12100"]
]

ROW_LABELS = [r[0] for r in TABLE_ROWS_RAW]


def _build_test_doc_graph(claims_text_list):
    """Membangun doc_graph terstandarisasi untuk CellLinker."""
    rows = []
    for r_idx, r_data in enumerate(TABLE_ROWS_RAW):
        row_cells = []
        r_lbl = r_data[0]
        for c_idx, val_str in enumerate(r_data):
            h_path = TABLE_HEADERS[c_idx]
            parsed = parse_academic_number(val_str)
            num_val = parsed[0] if parsed else None
            row_cells.append({
                "row": r_idx + 1,
                "col": c_idx + 1,
                "row_idx": r_idx,
                "col_idx": c_idx,
                "text": val_str,
                "raw_val": val_str,
                "num_val": num_val,
                "header_path": h_path,
                "row_label": r_lbl,
                "bbox": [50.0 + c_idx * 60, 100.0 + r_idx * 20, 50.0 + (c_idx + 1) * 60, 100.0 + (r_idx + 1) * 20]
            })
        rows.append(row_cells)

    table_dict = {
        "table_id": "Tabel_4_1",
        "page": 1,
        "table_num": "4.1",
        "normalized_id": "Tabel_4_1",
        "caption": "Tabel 4.1 Hasil Analisis Statistik Deskriptif",
        "bbox": [50.0, 90.0, 450.0, 250.0],
        "header_paths": TABLE_HEADERS,
        "num_rows": len(rows),
        "num_cols": len(TABLE_HEADERS),
        "rows": rows
    }

    claims = []
    for idx, c_text in enumerate(claims_text_list):
        claims.append({
            "claim_id": f"C_{idx + 1}",
            "page": 1,
            "text": c_text,
            "chapter": "BAB_4",
            "bbox": [50.0, 260.0 + idx * 25, 450.0, 280.0 + idx * 25]
        })

    return {
        "num_pages": 1,
        "detected_total_n": 96,
        "tables": [table_dict],
        "claims": claims,
        "page_dimensions": {1: [595.0, 842.0, 0, 0]}
    }


# =====================================================================
# TEST 1: Normalisasi desimal SPSS tanpa nol di depan
# =====================================================================
def test_spss_leading_decimal_normalization():
    p1 = parse_academic_number(",17")
    assert p1 is not None
    assert abs(p1[0] - 0.17) < 1e-6
    assert p1[1] == 2

    p2 = parse_academic_number("-,45")
    assert p2 is not None
    assert abs(p2[0] - (-0.45)) < 1e-6
    assert p2[1] == 2

    p3 = parse_academic_number(",00")
    assert p3 is not None
    assert abs(p3[0] - 0.0) < 1e-6
    assert p3[1] == 2

    p4 = parse_academic_number(".17")
    assert p4 is not None
    assert abs(p4[0] - 0.17) < 1e-6

    p5 = parse_academic_number("-.45")
    assert p5 is not None
    assert abs(p5[0] - (-0.45)) < 1e-6


# =====================================================================
# TEST 2: Heading 4.2.1.4 Likuiditas + Kalimat Pertama
# =====================================================================
def test_heading_likuiditas_sentence_1_binds_to_likuiditas():
    heading_text = "4.2.1.4 Likuiditas"
    sent_1 = "Hasil analisis deskriptif pada variabel likuiditas memiliki nilai minimum 0,17, artinya ukuran perusahaan yang mampu memenuhi kewajiban jangka pendek dengan asset lancarnya terkecil adalah 0,17."

    # 1. Unit level match_sentence_to_row
    matched_row = match_sentence_to_row(
        sent_1,
        ROW_LABELS,
        section_anchor_var="Likuiditas",
        table_rows_data=TABLE_ROWS_RAW
    )
    assert matched_row == "Likuiditas", f"Salah tertaut ke: {matched_row}"

    # 2. Quad Tuple level
    quads = extract_quad_tuples_from_sentence(
        sent_1,
        candidate_table_variables=ROW_LABELS,
        default_variable="Likuiditas",
        section_anchor_variable="Likuiditas"
    )
    assert len(quads) >= 1
    min_quad = [q for q in quads if q.stat_type == "MINIMUM"][0]
    assert min_quad.variable_name == "Likuiditas", f"Quad terbajak oleh: {min_quad.variable_name}"
    assert abs(min_quad.numeric_value - 0.17) < 1e-6

    res = verify_quad_tuple_against_table(min_quad, TABLE_HEADERS, TABLE_ROWS_RAW)
    assert res.status in ("VALID_EXACT", "VALID_ROUNDED"), f"Harusnya VALID, dapat {res.status}"

    # 3. Pipeline level CellLinker
    doc_graph = _build_test_doc_graph([heading_text, sent_1])
    linker = CellLinker()
    audit_res = linker.audit_document(doc_graph)
    findings = audit_res.get("findings", [])

    fatal_errors = [f for f in findings if f.get("verdict") not in ("PASS_EXACT_MATCH", "WARN_ROUNDING", "WARN_TRUNCATION_ROUNDING")]
    assert len(fatal_errors) == 0, f"Ditemukan false positive fatal: {fatal_errors}"

    pass_findings = [f for f in findings if f.get("verdict") == "PASS_EXACT_MATCH"]
    assert len(pass_findings) >= 1
    assert any(f.get("row_category") == "Likuiditas" for f in pass_findings)


# =====================================================================
# TEST 3: Kalimat Lanjutan di Bawah Heading Sama
# =====================================================================
def test_heading_likuiditas_sentence_2_binds_to_likuiditas():
    heading_text = "4.2.1.4 Likuiditas"
    sent_1 = "Hasil analisis deskriptif pada variabel likuiditas memiliki nilai minimum 0,17, artinya ukuran perusahaan yang mampu memenuhi kewajiban jangka pendek dengan asset lancarnya terkecil adalah 0,17."
    sent_2 = "Nilai maksimum sebesar 4,82, artinya ukuran perusahaan yang mampu memenuhi kewajiban jangka pendek dengan asset lancarnya terbesar adalah 4,82."

    # 1. Unit level match_sentence_to_row untuk sent_2
    matched_row = match_sentence_to_row(
        sent_2,
        ROW_LABELS,
        discourse_var="Likuiditas",
        section_anchor_var="Likuiditas",
        table_rows_data=TABLE_ROWS_RAW
    )
    assert matched_row == "Likuiditas", f"Salah tertaut ke: {matched_row}"

    # 2. Quad Tuple level untuk sent_2
    quads = extract_quad_tuples_from_sentence(
        sent_2,
        candidate_table_variables=ROW_LABELS,
        default_variable="Likuiditas",
        section_anchor_variable="Likuiditas"
    )
    assert len(quads) >= 1
    max_quad = [q for q in quads if q.stat_type == "MAXIMUM"][0]
    assert max_quad.variable_name == "Likuiditas", f"Quad terbajak oleh: {max_quad.variable_name}"
    assert abs(max_quad.numeric_value - 4.82) < 1e-6

    res = verify_quad_tuple_against_table(max_quad, TABLE_HEADERS, TABLE_ROWS_RAW)
    assert res.status in ("VALID_EXACT", "VALID_ROUNDED"), f"Harusnya VALID, dapat {res.status}"

    # 3. Pipeline level CellLinker untuk kedua kalimat berturut-turut
    doc_graph = _build_test_doc_graph([heading_text, sent_1, sent_2])
    linker = CellLinker()
    audit_res = linker.audit_document(doc_graph)
    findings = audit_res.get("findings", [])

    fatal_errors = [f for f in findings if f.get("verdict") not in ("PASS_EXACT_MATCH", "WARN_ROUNDING", "WARN_TRUNCATION_ROUNDING")]
    assert len(fatal_errors) == 0, f"Ditemukan false positive fatal: {fatal_errors}"

    pass_findings = [f for f in findings if f.get("verdict") == "PASS_EXACT_MATCH"]
    # Harus ada verifikasi lolos untuk Likuiditas
    assert any(f.get("row_category") == "Likuiditas" and "4,82" in f.get("claim_value_display", "") for f in pass_findings)


# =====================================================================
# TEST 4: Tes Negatif (Real Error Tetap Tertangkap pada Likuiditas)
# =====================================================================
def test_negative_real_error_flagged_on_likuiditas():
    heading_text = "4.2.1.4 Likuiditas"
    wrong_sent = "Nilai maksimum sebesar 9,99, artinya ukuran perusahaan yang mampu memenuhi kewajiban jangka pendek dengan asset lancarnya terbesar adalah 9,99."

    # 1. Unit level match_sentence_to_row wajib tertaut ke Likuiditas
    matched_row = match_sentence_to_row(
        wrong_sent,
        ROW_LABELS,
        discourse_var="Likuiditas",
        section_anchor_var="Likuiditas",
        table_rows_data=TABLE_ROWS_RAW
    )
    assert matched_row == "Likuiditas", f"Harusnya terikat ke Likuiditas, bukan: {matched_row}"

    # 2. Quad Tuple level wajib terikat ke Likuiditas
    quads = extract_quad_tuples_from_sentence(
        wrong_sent,
        candidate_table_variables=ROW_LABELS,
        default_variable="Likuiditas",
        section_anchor_variable="Likuiditas"
    )
    assert len(quads) >= 1
    max_quad = [q for q in quads if q.stat_type == "MAXIMUM"][0]
    assert max_quad.variable_name == "Likuiditas", f"Harusnya Likuiditas, bukan: {max_quad.variable_name}"
    assert abs(max_quad.numeric_value - 9.99) < 1e-6

    # 3. Pipeline level CellLinker wajib menerbitkan FATAL mismatch pada Likuiditas (9,99 vs 4,82)
    doc_graph = _build_test_doc_graph([heading_text, wrong_sent])
    linker = CellLinker()
    audit_res = linker.audit_document(doc_graph)
    findings = audit_res.get("findings", [])

    fatal_errors = [f for f in findings if f.get("verdict") not in ("PASS_EXACT_MATCH", "WARN_ROUNDING", "WARN_TRUNCATION_ROUNDING")]
    assert len(fatal_errors) >= 1, "Harusnya terdeteksi kesalahan nyata, tapi lolos!"

    target_err = fatal_errors[0]
    assert target_err.get("row_category") == "Likuiditas", f"Harusnya tertaut ke Likuiditas, tapi: {target_err.get('row_category')}"
    assert "9,99" in target_err.get("claim_value_display", "")
    assert "4,82" in str(target_err.get("table_value_display", ""))
