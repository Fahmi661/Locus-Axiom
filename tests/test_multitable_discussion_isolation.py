"""
Regression tests for Multi-Table Discussion Isolation (5-Stage Fix):
1. stitch_cross_page_tables refuses to merge distinct numbered tables / tables ending in Total / mid-page tables.
2. parse_spss_frequency_table stops at TOTAL and never overwrites valid categories.
3. Parenthesized '(Sumber: ...)' footnotes are filtered out and numbered survey items ('3) ...') act as scope barriers.
4. Table-Topic Affinity Gate routes demographic/entity discussions to the matching table (not previous table).
5. Paragraph table anchor propagation, SPSS '1 :: ' prefix stripping, and alpha threshold 0.05 guard.
6. End-to-end verification on real bab4.pdf (zero stitched-table fatal false positives on Tabel IV.8 & Tabel IV.10).
"""

import os
import pytest

from backend.layer1_perception.table_geometry import TableGeometryExtractor
from backend.layer1_perception.pdf_reader import FastPdfReader
from backend.layer2_core.cell_linker import CellLinker
from src.core.spss_likert_engine import parse_spss_frequency_table, resolve_table_with_ref_check
from src.core.quad_tuple_verifier import (
    normalize_variable_stem,
    extract_quad_tuples_from_sentence,
)


def _make_spss_likert_table(table_id: str, norm_id: str, caption: str, page: int, bbox, s_val: int, ss_val: int, ts_val: int = 8, n_val: int = 11):
    headers = ["Valid", "Kategori", "Frequency", "Percent", "Valid Percent", "Cumulative Percent"]
    raw_rows = [
        ["Valid", "TS", str(ts_val), f"{ts_val:.1f}", f"{ts_val:.1f}", f"{ts_val:.1f}"],
        ["", "N", str(n_val), f"{n_val:.1f}", f"{n_val:.1f}", f"{ts_val + n_val:.1f}"],
        ["", "S", str(s_val), f"{s_val:.1f}", f"{s_val:.1f}", f"{ts_val + n_val + s_val:.1f}"],
        ["", "SS", str(ss_val), f"{ss_val:.1f}", f"{ss_val:.1f}", "100.0"],
        ["", "Total", "100", "100.0", "100.0", ""],
    ]
    rows = []
    for r_i, rr in enumerate(raw_rows):
        row_cells = []
        for c_i, val in enumerate(rr):
            nv = None
            try:
                nv = float(val)
            except ValueError:
                pass
            row_cells.append({
                "row": r_i + 1,
                "col": c_i + 1,
                "row_idx": r_i,
                "col_idx": c_i,
                "row_label": rr[1],
                "raw_val": val,
                "text": val,
                "header_path": headers[c_i],
                "num_val": nv,
                "bbox": [bbox[0] + c_i * 55, bbox[1] + r_i * 16, bbox[0] + (c_i + 1) * 55 - 2, bbox[1] + (r_i + 1) * 16 - 2],
                "cell_rect": [bbox[0] + c_i * 55, bbox[1] + r_i * 16, bbox[0] + (c_i + 1) * 55 - 2, bbox[1] + (r_i + 1) * 16 - 2],
                "bbox_approx": False,
            })
        rows.append(row_cells)
    return {
        "table_id": table_id,
        "table_num": norm_id,
        "normalized_id": norm_id,
        "caption": caption,
        "page": page,
        "page_height_pt": 842.0,
        "y_bottom": bbox[3],
        "bbox": list(bbox),
        "num_rows": len(rows),
        "num_cols": len(headers),
        "table_type": "SPSS_LIKERT_FREQ",
        "header_paths": headers,
        "rows": rows,
    }


def test_stitch_cross_page_refuses_distinct_numbered_spss_tables_and_total_rows():
    """Stage 1: Two separate SPSS Likert tables on consecutive pages with identical margins MUST NOT be stitched."""
    t_8 = _make_spss_likert_table(
        "Tabel_4_8", "4.8", "Tabel IV.8 Tanggapan Responden Pernyataan X1.3",
        page=6, bbox=[100.0, 488.0, 460.0, 572.0], s_val=48, ss_val=33, ts_val=8, n_val=11,
    )
    t_9 = _make_spss_likert_table(
        "Tabel_4_9", "4.9", "Tabel IV.9 Tanggapan Responden Pernyataan X1.4",
        page=7, bbox=[100.0, 210.0, 460.0, 295.0], s_val=49, ss_val=34, ts_val=2, n_val=15,
    )

    stitched = TableGeometryExtractor.stitch_cross_page_tables([t_8, t_9])
    assert len(stitched) == 2, f"Expected 2 distinct tables, got {len(stitched)}"
    assert stitched[0]["table_id"] == "Tabel_4_8"
    assert stitched[1]["table_id"] == "Tabel_4_9"
    assert not stitched[0].get("is_cross_page")


def test_spss_parser_stops_at_total_and_never_overwrites_categories():
    """Stage 1: Even if duplicate Likert rows follow a Total row, parse_spss_frequency_table keeps the first block."""
    headers = ["Valid", "Kategori", "Frequency", "Percent", "Valid Percent", "Cumulative Percent"]
    rows = [
        ["Valid", "TS", "8", "8.0", "8.0", "8.0"],
        ["", "N", "11", "11.0", "11.0", "19.0"],
        ["", "S", "48", "48.0", "48.0", "67.0"],
        ["", "SS", "33", "33.0", "33.0", "100.0"],
        ["", "Total", "100", "100.0", "100.0", ""],
        # Stray second block (e.g. from another table) must NEVER overwrite S=48 / SS=33
        ["Valid", "S", "49", "49.0", "49.0", "66.0"],
        ["", "SS", "34", "34.0", "34.0", "100.0"],
    ]
    cleaned = parse_spss_frequency_table(headers, rows)
    assert cleaned["S"].cells["FREQUENCY"] == 48.0
    assert cleaned["SS"].cells["FREQUENCY"] == 33.0


def test_table_topic_affinity_routes_usia_to_usia_table_not_gender():
    """Stage 3: Discussion about 'interval usia 48-58 tahun' routes to Tabel 4.2 Usia, not Tabel 4.1 Jenis Kelamin."""
    t_gender = {
        "table_id": "Tabel_4_1",
        "normalized_id": "4.1",
        "caption": "Tabel 4.1 Jumlah Responden Berdasarkan Jenis Kelamin",
        "page": 6,
        "y_bottom": 500.0,
        "bbox": [50.0, 300.0, 500.0, 500.0],
        "table_type": "GENERAL_TABLE",
        "header_paths": ["Jenis Kelamin", "Jumlah", "Persentase"],
        "rows": [
            [
                {"row": 1, "col": 1, "row_label": "Laki-laki", "raw_val": "Laki-laki", "header_path": "Jenis Kelamin", "num_val": None},
                {"row": 1, "col": 2, "row_label": "Laki-laki", "raw_val": "33", "header_path": "Jumlah", "num_val": 33.0},
                {"row": 1, "col": 3, "row_label": "Laki-laki", "raw_val": "33%", "header_path": "Persentase", "num_val": 33.0},
            ],
            [
                {"row": 2, "col": 1, "row_label": "Wanita", "raw_val": "Wanita", "header_path": "Jenis Kelamin", "num_val": None},
                {"row": 2, "col": 2, "row_label": "Wanita", "raw_val": "67", "header_path": "Jumlah", "num_val": 67.0},
                {"row": 2, "col": 3, "row_label": "Wanita", "raw_val": "67%", "header_path": "Persentase", "num_val": 67.0},
            ],
        ],
    }
    t_usia = {
        "table_id": "Tabel_4_2",
        "normalized_id": "4.2",
        "caption": "Tabel 4.2 Jumlah Responden Berdasarkan Usia",
        "page": 7,
        "y_bottom": 350.0,
        "bbox": [50.0, 150.0, 500.0, 350.0],
        "table_type": "GENERAL_TABLE",
        "header_paths": ["Usia", "Jumlah", "Persentase"],
        "rows": [
            [
                {"row": 1, "col": 1, "row_label": "17-27 tahun", "raw_val": "17-27 tahun", "header_path": "Usia", "num_val": None},
                {"row": 1, "col": 2, "row_label": "17-27 tahun", "raw_val": "45", "header_path": "Jumlah", "num_val": 45.0},
                {"row": 1, "col": 3, "row_label": "17-27 tahun", "raw_val": "45%", "header_path": "Persentase", "num_val": 45.0},
            ],
            [
                {"row": 2, "col": 1, "row_label": "48-58 tahun", "raw_val": "48-58 tahun", "header_path": "Usia", "num_val": None},
                {"row": 2, "col": 2, "row_label": "48-58 tahun", "raw_val": "3", "header_path": "Jumlah", "num_val": 3.0},
                {"row": 2, "col": 3, "row_label": "48-58 tahun", "raw_val": "3%", "header_path": "Persentase", "num_val": 3.0},
            ],
        ],
    }

    linker = CellLinker()
    claim = {
        "claim_id": "C_USIA_1",
        "page": 7,
        "claim_y_top": 380.0,
        "scope_table_id": "Tabel_4_1",  # Stale wrong scope from previous page
        "text": "Sedangkan jumlah responden terendah ada pada interval usia 48-58 tahun yaitu sebanyak 3 responden (3%).",
    }
    findings = linker.link_claim_to_table(claim, [t_gender, t_usia])
    fatals = [f for f in findings if f.get("verdict") != "PASS_EXACT_MATCH"]
    assert len(fatals) == 0, f"Should NOT flag false contradiction against Jenis Kelamin: {fatals}"


def test_spss_model_prefix_stripping_and_alpha_005_threshold_guard():
    """Stage 4: '1 :: OPM' normalizes to 'opm', and 'tingkat signifikansi (α) = 0,05' is never extracted as empirical Sig."""
    assert normalize_variable_stem("1 :: OPM") == "opm"
    assert normalize_variable_stem("1 :: LN_ROE") == "roe"
    assert normalize_variable_stem("Skala\nAwal") == "skala awal"

    sent_alpha = "Pada penelitian ini analisis regresi berganda menggunakan tingkat signifikansi (α) sebesar 0,05 (5%)."
    quads_alpha = extract_quad_tuples_from_sentence(sent_alpha, candidate_table_variables=["1 :: OPM", "1 :: LN_ROE"])
    assert len(quads_alpha) == 0, f"Alpha threshold 0.05 leaked as empirical quad: {quads_alpha}"

    sent_hyp = "3. Penguji Hipotesis 3 Pengaruh OPM terhadap nilai perusahaan menghasilkan nilai Sig. sebesar 0,497 > 0,05."
    quads_hyp = extract_quad_tuples_from_sentence(sent_hyp, candidate_table_variables=["1 :: LN_ROE", "1 :: OPM"])
    assert len(quads_hyp) == 1
    assert quads_hyp[0].variable_name == "1 :: OPM"
    assert abs(quads_hyp[0].numeric_value - 0.497) < 1e-6


def test_paragraph_anchor_propagates_across_multi_sentence_hypothesis_discussion():
    """Stage 3 + 4: Multi-page hypothesis discussion anchored to Tabel 4.10 resolves OPM/NPM cleanly without cross-table bleed."""
    t_anova = {
        "table_id": "Tabel_4_9",
        "normalized_id": "4.9",
        "caption": "Tabel 4.9 Hasil Uji F (ANOVA)",
        "page": 11,
        "y_bottom": 400.0,
        "bbox": [50.0, 200.0, 500.0, 400.0],
        "table_type": "REGRESSION_COEFF",
        "header_paths": ["Model", "F", "Sig."],
        "rows": [
            [
                {"row": 1, "col": 1, "row_label": "Regression", "raw_val": "Regression", "header_path": "Model", "num_val": None},
                {"row": 1, "col": 2, "row_label": "Regression", "raw_val": "5.120", "header_path": "F", "num_val": 5.12},
                {"row": 1, "col": 3, "row_label": "Regression", "raw_val": ".002", "header_path": "Sig.", "num_val": 0.002},
            ]
        ],
    }
    t_coeff = {
        "table_id": "Tabel_4_10",
        "normalized_id": "4.10",
        "caption": "Tabel 4.10 Uji Parsial (Uji t)",
        "page": 13,
        "y_bottom": 450.0,
        "bbox": [50.0, 200.0, 500.0, 450.0],
        "table_type": "REGRESSION_COEFF",
        "header_paths": ["Model", "B", "t", "Sig."],
        "rows": [
            [
                {"row": 1, "col": 1, "row_label": "1 :: LN_ROE", "raw_val": "1 :: LN_ROE", "header_path": "Model", "num_val": None},
                {"row": 1, "col": 2, "row_label": "1 :: LN_ROE", "raw_val": ".115", "header_path": "B", "num_val": 0.115},
                {"row": 1, "col": 3, "row_label": "1 :: LN_ROE", "raw_val": "1.260", "header_path": "t", "num_val": 1.26},
                {"row": 1, "col": 4, "row_label": "1 :: LN_ROE", "raw_val": ".211", "header_path": "Sig.", "num_val": 0.211},
            ],
            [
                {"row": 2, "col": 1, "row_label": "1 :: OPM", "raw_val": "1 :: OPM", "header_path": "Model", "num_val": None},
                {"row": 2, "col": 2, "row_label": "1 :: OPM", "raw_val": ".082", "header_path": "B", "num_val": 0.082},
                {"row": 2, "col": 3, "row_label": "1 :: OPM", "raw_val": ".684", "header_path": "t", "num_val": 0.684},
                {"row": 2, "col": 4, "row_label": "1 :: OPM", "raw_val": ".497", "header_path": "Sig.", "num_val": 0.497},
            ],
        ],
    }

    doc_graph = {
        "document_id": "HYP-ANCHOR-TEST",
        "render_scale": 1.5,
        "tables": [t_anova, t_coeff],
        "claims": [
            {
                "claim_id": "C_14_1",
                "page": 14,
                "claim_y_top": 120.0,
                "scope_table_id": "Tabel_4_10",
                "text": "2. Penguji Hipotesis 2 berdasarkan Tabel 4.10, pengaruh ROE memperoleh nilai Sig. sebesar 0,211 > 0,05.",
            },
            {
                "claim_id": "C_15_1",
                "page": 15,
                "claim_y_top": 300.0,
                "scope_table_id": None,  # Spilled onto page 15 without repeating "Tabel 4.10"
                "text": "3. Penguji Hipotesis 3 pengaruh OPM memperoleh nilai Sig. sebesar 0,497 > 0,05.",
            },
        ],
        "page_dimensions": {11: [595.0, 842.0, 0.0, 0.0], 13: [595.0, 842.0, 0.0, 0.0], 14: [595.0, 842.0, 0.0, 0.0], 15: [595.0, 842.0, 0.0, 0.0]},
    }
    bundle = CellLinker().audit_document(doc_graph)
    fatals = [f for f in bundle["findings"] if f.get("verdict") != "PASS_EXACT_MATCH"]
    assert len(fatals) == 0, f"Unexpected false contradiction in multi-page hypothesis discussion: {fatals}"


def test_real_bab4_pdf_zero_false_stitched_fatal_errors():
    """End-to-end verification on real bab4.pdf from user screenshots (Tabel IV.8 & Tabel IV.10)."""
    bab4_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "uploads", "bab4.pdf",
    )
    if not os.path.exists(bab4_path):
        pytest.skip("bab4.pdf not present in workspace")

    doc_graph = FastPdfReader.process_pdf(bab4_path)
    # Previously 18 tables were wrongly swallowed (65 -> 47); now >= 60 distinct tables must remain intact
    assert len(doc_graph["tables"]) >= 60, f"Expected >= 60 distinct tables, got {len(doc_graph['tables'])}"

    # Verify parenthesized '(Sumber: ...)' footnotes are no longer glued onto claims
    sumber_claims = [c for c in doc_graph["claims"] if c["text"].lstrip().lower().startswith("(sumber")]
    assert len(sumber_claims) == 0, f"Found unstripped (Sumber: ...) prefix on claims: {sumber_claims[:3]}"

    bundle = CellLinker().audit_document(doc_graph)
    findings = bundle["findings"]
    # Tabel IV.8 (Hal. 6: S=48, SS=33), Tabel IV.10 (Hal. 7-8: S=45, SS=43),
    # AND Tabel IV.5 Statistik Deskriptif (Hal. 4: N=100, Mean=40.90/39.99/41.90/41.53)
    # must have ZERO false fatal errors across the entire 53-page thesis!
    fatal_errors = [
        f for f in findings
        if f.get("verdict") not in ("PASS_EXACT_MATCH", "TABLE_REFERENCE_TYPO")
        and "WARN" not in f.get("verdict", "")
    ]
    assert len(fatal_errors) == 0, f"Expected 0 false fatal errors across bab4.pdf, got: {fatal_errors}"


def test_multitier_grim_n100_and_parallel_masing_masing_clause():
    """
    Verifies the exact Tabel IV.5 Statistik Deskriptif case:
    1. 'Descriptive Statistics :: N' = 100 is read accurately (no false GRIM N=15 on 40,90 or 39,99).
    2. Parallel 'Disiplin kerja dan kinerja karyawan memiliki rata-rata masing-masing 41,90 dan 41,53
       dengan standar deviasi 4,505 dan 4,343' binds 41,90->Disiplin Kerja.MEAN, 41,53->Kinerja Karyawan.MEAN,
       4,505->Disiplin Kerja.STD, 4,343->Kinerja Karyawan.STD with 0 COLUMN_SWAP_ERROR.
    3. make_highlighted_clause never slices inside Indonesian decimal commas ('41,90', '4,646').
    """
    from backend.layer2_core.cell_linker import make_highlighted_clause

    tbl_desc = {
        "table_id": "Tabel_4_5",
        "normalized_id": "4.5",
        "caption": "Tabel IV.5 Statistik Deskriptif",
        "page": 4,
        "y_bottom": 420.0,
        "bbox": [60.0, 220.0, 520.0, 420.0],
        "table_type": "DESCRIPTIVE_STATS",
        "header_paths": [
            "Descriptive Statistics",
            "Descriptive Statistics :: N",
            "Descriptive Statistics :: Minimum",
            "Descriptive Statistics :: Maximum",
            "Descriptive Statistics :: Mean",
            "Descriptive Statistics :: Std. Deviation",
        ],
        "rows": [
            [
                {"row": r_i + 1, "col": c_i + 1, "row_label": r[0], "raw_val": val,
                 "header_path": [
                     "Descriptive Statistics",
                     "Descriptive Statistics :: N",
                     "Descriptive Statistics :: Minimum",
                     "Descriptive Statistics :: Maximum",
                     "Descriptive Statistics :: Mean",
                     "Descriptive Statistics :: Std. Deviation",
                 ][c_i],
                 "num_val": float(val.replace(",", ".")) if c_i > 0 else None}
                for c_i, val in enumerate(r)
            ]
            for r_i, r in enumerate([
                ["Budaya Organisasi", "100", "28", "48", "40,90", "4,646"],
                ["Kompensasi", "100", "21", "49", "39,99", "5,795"],
                ["Disiplin Kerja", "100", "28", "49", "41,90", "4,505"],
                ["Kinerja Karyawan", "100", "30", "49", "41,53", "4,343"],
            ])
        ],
    }

    doc_graph = {
        "document_id": "DESC-IV5-TEST",
        "detected_total_n": 15,  # Deliberate bogus global N=15 trap! Must NOT override row N=100!
        "tables": [tbl_desc],
        "claims": [
            {
                "claim_id": "C_4_1",
                "page": 4,
                "claim_y_top": 450.0,
                "scope_table_id": "Tabel_4_5",
                "text": "Berdasarkan statistik deskriptif untuk 100 responden, budaya organisasi memiliki nilai rata-rata 40,90 dengan standar deviasi 4,646, menunjukkan variasi yang moderat.",
            },
            {
                "claim_id": "C_4_2",
                "page": 4,
                "claim_y_top": 480.0,
                "scope_table_id": "Tabel_4_5",
                "text": "Kompensasi memiliki rata-rata 39,99 dan standar deviasi 5,795, menunjukkan variasi yang lebih besar dibandingkan dengan variabel lain.",
            },
            {
                "claim_id": "C_4_3",
                "page": 4,
                "claim_y_top": 510.0,
                "scope_table_id": "Tabel_4_5",
                "text": "Disiplin kerja dan kinerja karyawan memiliki rata-rata masing-masing 41,90 dan 41,53 dengan standar deviasi 4,505 dan 4,343, menunjukkan variasi yang relatif rendah.",
            },
        ],
        "page_dimensions": {4: [595.0, 842.0, 0.0, 0.0]},
    }

    bundle = CellLinker().audit_document(doc_graph)
    fatals = [f for f in bundle["findings"] if f.get("verdict") != "PASS_EXACT_MATCH"]
    assert len(fatals) == 0, f"Expected 0 false positives on Tabel IV.5, got: {fatals}"
    passes = [f for f in bundle["findings"] if f.get("verdict") == "PASS_EXACT_MATCH"]
    assert len(passes) >= 8, f"Expected all 8 mean/std values to verify as PASS_EXACT_MATCH, got {len(passes)}"

    # Quote slicer must never cut inside decimal commas ('41,90' or '4,646')
    hl = make_highlighted_clause(
        "Disiplin kerja dan kinerja karyawan memiliki rata-rata masing-masing 41,90 dan 41,53 dengan standar deviasi 4,505 dan 4,343, menunjukkan variasi yang relatif rendah.",
        "41,53",
    )
    assert "41,90" in hl and "4,505" in hl and "4,343" in hl


def test_parenthesized_t_tabel_and_verbal_negative_magnitude():
    """
    Verifies:
    1. Parenthesized critical thresholds 't tabel (1,960)' are ignored and never flagged as STAT_TEST mismatch.
    2. Verbal negative delta 'terjadi penurunan sebesar 0,67%' matches cell '-0,67%' cleanly.
    """
    from src.core.quad_tuple_verifier import verify_quad_tuple_against_table

    sent_ttab = "Diketahui pula, nilai Sig. Z1 (0,898) > 0,05 dan nilai t hitung (-0,129) < t tabel (1,960) maka H0 diterima."
    quads = extract_quad_tuples_from_sentence(sent_ttab, candidate_table_variables=["(Constant) :: Z1"])
    vals = [round(q.numeric_value, 4) for q in quads]
    assert 1.96 not in vals and 0.05 not in vals, f"Critical thresholds leaked: {quads}"

    sent_neg = "Pada kelas kontrol terjadi penurunan kesiapan kerja sebesar 0,67% yang ditunjukkan dengan tanda minus."
    q_neg = extract_quad_tuples_from_sentence(sent_neg, candidate_table_variables=["Kontrol"])
    assert len(q_neg) == 1
    res = verify_quad_tuple_against_table(
        q_neg[0],
        ["Kelas", "Persentase Perbedaan"],
        [["Kontrol", "-0,67%"]],
    )
    assert res.status == "VALID_EXACT", f"Expected VALID_EXACT for verbal negative magnitude, got {res.status}"

