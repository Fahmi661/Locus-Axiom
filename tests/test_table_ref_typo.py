import pytest
from backend.layer2_core.cell_linker import CellLinker


def test_table_reference_typo_case():
    """
    Uji kasus nyata Tabel IV.7 (SS=31) dengan teks salah rujuk 'Menurut tabel IV.6... 31 responden (31%) sangat setuju'
    vs Tabel IV.6 (SS=32).
    Hasilnya WAJIB 0 fatal error angka dan 1 peringatan TABLE_REFERENCE_TYPO.
    """
    t_iv6 = {
        "table_id": "Tabel_4_6",
        "table_num": "4.6",
        "normalized_id": "4.6",
        "caption": "Tabel IV.6 Tanggapan Responden Variabel X1",
        "page": 4,
        "y_bottom": 280.0,
        "bbox": [50, 80, 500, 280],
        "table_type": "SPSS_LIKERT_FREQ",
        "header_paths": ["Kategori", "Frequency", "Percent", "Valid Percent", "Cumulative Percent"],
        "rows": [
            [
                {"row": 1, "col": 1, "raw_val": "STS", "row_label": "STS", "header_path": "Kategori", "num_val": None},
                {"row": 1, "col": 2, "raw_val": "2", "row_label": "STS", "header_path": "Frequency", "num_val": 2.0},
                {"row": 1, "col": 3, "raw_val": "2.0", "row_label": "STS", "header_path": "Percent", "num_val": 2.0},
                {"row": 1, "col": 4, "raw_val": "2.0", "row_label": "STS", "header_path": "Valid Percent", "num_val": 2.0},
                {"row": 1, "col": 5, "raw_val": "2.0", "row_label": "STS", "header_path": "Cumulative Percent", "num_val": 2.0}
            ],
            [
                {"row": 2, "col": 1, "raw_val": "SS", "row_label": "SS", "header_path": "Kategori", "num_val": None},
                {"row": 2, "col": 2, "raw_val": "32", "row_label": "SS", "header_path": "Frequency", "num_val": 32.0},
                {"row": 2, "col": 3, "raw_val": "32.0", "row_label": "SS", "header_path": "Percent", "num_val": 32.0},
                {"row": 2, "col": 4, "raw_val": "32.0", "row_label": "SS", "header_path": "Valid Percent", "num_val": 32.0},
                {"row": 2, "col": 5, "raw_val": "100.0", "row_label": "SS", "header_path": "Cumulative Percent", "num_val": 100.0}
            ]
        ]
    }

    t_iv7 = {
        "table_id": "Tabel_4_7",
        "table_num": "4.7",
        "normalized_id": "4.7",
        "caption": "Tabel IV.7 Tanggapan Responden Variabel X2",
        "page": 4,
        "y_bottom": 580.0,
        "bbox": [50, 380, 500, 580],
        "table_type": "SPSS_LIKERT_FREQ",
        "header_paths": ["Kategori", "Frequency", "Percent", "Valid Percent", "Cumulative Percent"],
        "rows": [
            [
                {"row": 1, "col": 1, "raw_val": "STS", "row_label": "STS", "header_path": "Kategori", "num_val": None},
                {"row": 1, "col": 2, "raw_val": "1", "row_label": "STS", "header_path": "Frequency", "num_val": 1.0},
                {"row": 1, "col": 3, "raw_val": "1.0", "row_label": "STS", "header_path": "Percent", "num_val": 1.0},
                {"row": 1, "col": 4, "raw_val": "1.0", "row_label": "STS", "header_path": "Valid Percent", "num_val": 1.0},
                {"row": 1, "col": 5, "raw_val": "1.0", "row_label": "STS", "header_path": "Cumulative Percent", "num_val": 1.0}
            ],
            [
                {"row": 2, "col": 1, "raw_val": "SS", "row_label": "SS", "header_path": "Kategori", "num_val": None},
                {"row": 2, "col": 2, "raw_val": "31", "row_label": "SS", "header_path": "Frequency", "num_val": 31.0},
                {"row": 2, "col": 3, "raw_val": "31.0", "row_label": "SS", "header_path": "Percent", "num_val": 31.0},
                {"row": 2, "col": 4, "raw_val": "31.0", "row_label": "SS", "header_path": "Valid Percent", "num_val": 31.0},
                {"row": 2, "col": 5, "raw_val": "100.0", "row_label": "SS", "header_path": "Cumulative Percent", "num_val": 100.0}
            ]
        ]
    }

    tables = [t_iv6, t_iv7]
    linker = CellLinker()

    claim = {
        "claim_id": "C_4_7_1",
        "page": 4,
        "claim_y_top": 600.0,
        "scope_table_id": "Tabel_4_7",
        "text": "Menurut tabel IV.6, sebanyak 31 responden (31%) menyatakan sangat setuju."
    }

    findings = linker.link_claim_to_table(claim, tables)

    # 1. Pastikan ada 1 peringatan TABLE_REFERENCE_TYPO
    typo_findings = [f for f in findings if f.get("verdict") == "TABLE_REFERENCE_TYPO"]
    assert len(typo_findings) == 1, f"Harus ada 1 peringatan TABLE_REFERENCE_TYPO, temuan: {findings}"
    assert typo_findings[0].get("severity") == "MEDIUM"
    assert "Salah nomor rujukan tabel" in typo_findings[0].get("human_explanation", "")

    # 2. Pastikan 0 fatal error angka
    fatal_errors = [
        f for f in findings
        if f.get("severity") in ("HIGH", "FATAL")
        or "CONTRADICTION" in f.get("verdict", "")
        or "MISMATCH" in f.get("verdict", "")
        or "ERROR" in f.get("verdict", "")
    ]
    assert len(fatal_errors) == 0, f"Harus 0 fatal error angka, namun ditemukan: {fatal_errors}"

    # 3. Pastikan klaim berhasil lolos verifikasi (PASS) terhadap Tabel IV.7
    pass_findings = [f for f in findings if f.get("verdict") == "PASS_EXACT_MATCH"]
    assert len(pass_findings) >= 1, "Harus ada hasil verifikasi konsisten (PASS_EXACT_MATCH) terhadap Tabel IV.7"
    for pf in pass_findings:
        assert pf.get("table_evidence", {}).get("table_id") == "Tabel_4_7"
