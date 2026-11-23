import pytest
from backend.layer2_core.cell_linker import CellLinker


@pytest.fixture
def sample_tables():
    t1 = {
        "table_id": "Tabel_4_1",
        "table_num": "4.1",
        "normalized_id": "4.1",
        "page": 4,
        "table_type": "DESCRIPTIVE_STATS",
        "caption": "Tabel 4.1 Statistik Deskriptif",
        "header_paths": ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Deviation"],
        "rows": [
            [
                {"row": 1, "col": 1, "text": "Likuiditas", "raw_val": "Likuiditas", "row_label": "Likuiditas", "header_path": "Variabel", "num_val": None},
                {"row": 1, "col": 2, "text": "96", "raw_val": "96", "row_label": "Likuiditas", "header_path": "N", "num_val": 96.0},
                {"row": 1, "col": 3, "text": ",17", "raw_val": ",17", "row_label": "Likuiditas", "header_path": "Minimum", "num_val": 0.17},
                {"row": 1, "col": 4, "text": "4,82", "raw_val": "4,82", "row_label": "Likuiditas", "header_path": "Maximum", "num_val": 4.82},
                {"row": 1, "col": 5, "text": "1,4831", "raw_val": "1,4831", "row_label": "Likuiditas", "header_path": "Mean", "num_val": 1.4831},
                {"row": 1, "col": 6, "text": "1,29417", "raw_val": "1,29417", "row_label": "Likuiditas", "header_path": "Std. Deviation", "num_val": 1.29417}
            ]
        ]
    }

    t2 = {
        "table_id": "Tabel_4_2",
        "table_num": "4.2",
        "normalized_id": "4.2",
        "page": 5,
        "table_type": "REGRESSION_COEFF",
        "caption": "Tabel 4.2 Hasil Uji Regresi",
        "header_paths": ["Model", "B", "Std. Error", "Beta", "t", "Sig."],
        "rows": [
            [
                {"row": 1, "col": 1, "text": "Ukuran Perusahaan", "raw_val": "Ukuran Perusahaan", "row_label": "Ukuran Perusahaan", "header_path": "Model", "num_val": None},
                {"row": 1, "col": 2, "text": "12,55", "raw_val": "12,55", "row_label": "Ukuran Perusahaan", "header_path": "B", "num_val": 12.55},
                {"row": 1, "col": 3, "text": "0,45", "raw_val": "0,45", "row_label": "Ukuran Perusahaan", "header_path": "Std. Error", "num_val": 0.45},
                {"row": 1, "col": 4, "text": "0,32", "raw_val": "0,32", "row_label": "Ukuran Perusahaan", "header_path": "Beta", "num_val": 0.32},
                {"row": 1, "col": 5, "text": "2,78", "raw_val": "2,78", "row_label": "Ukuran Perusahaan", "header_path": "t", "num_val": 2.78},
                {"row": 1, "col": 6, "text": "0,007", "raw_val": "0,007", "row_label": "Ukuran Perusahaan", "header_path": "Sig.", "num_val": 0.007}
            ],
            [
                {"row": 2, "col": 1, "text": "Likuiditas", "raw_val": "Likuiditas", "row_label": "Likuiditas", "header_path": "Model", "num_val": None},
                {"row": 2, "col": 2, "text": "2,50", "raw_val": "2,50", "row_label": "Likuiditas", "header_path": "B", "num_val": 2.50},
                {"row": 2, "col": 3, "text": "0,15", "raw_val": "0,15", "row_label": "Likuiditas", "header_path": "Std. Error", "num_val": 0.15},
                {"row": 2, "col": 4, "text": "0,18", "raw_val": "0,18", "row_label": "Likuiditas", "header_path": "Beta", "num_val": 0.18},
                {"row": 2, "col": 5, "text": "1,65", "raw_val": "1,65", "row_label": "Likuiditas", "header_path": "t", "num_val": 1.65},
                {"row": 2, "col": 6, "text": "0,102", "raw_val": "0,102", "row_label": "Likuiditas", "header_path": "Sig.", "num_val": 0.102}
            ]
        ]
    }
    return [t1, t2]


def test_scope_isolation_no_leak(sample_tables):
    """
    1. Isolasi Tabel 4.2 tidak bocor ke 4.1:
    Klaim dalam scope Tabel 4.2 (tanpa rujukan tabel eksplisit) harus dievaluasi
    HANYA terhadap Tabel 4.2, tidak boleh mencocokkan atau bocor ke Tabel 4.1.
    """
    linker = CellLinker()
    claim_t2 = {
        "claim_id": "C_5_1",
        "page": 5,
        "text": "Nilai t hitung pada variabel ukuran perusahaan adalah sebesar 2,78.",
        "scope_table_id": "Tabel_4_2"
    }

    findings = linker.link_claim_to_table(claim_t2, sample_tables)
    assert len(findings) > 0, "Klaim harus tertaut ke Tabel 4.2"
    for f in findings:
        tbl_id = f.get("table_evidence", {}).get("table_id")
        assert tbl_id == "Tabel_4_2", f"Klaim bocor ke {tbl_id}, seharusnya tetap di Tabel_4_2"
        assert "Tabel 4.1" not in f.get("table_ref", "")


def test_explicit_reference_penetrates_scope(sample_tables):
    """
    2. Rujukan eksplisit 'Tabel 4.1' menembus zona:
    Walaupun klaim berada pada zona halaman/scope Tabel 4.2, jika teks secara
    eksplisit menyebut 'Tabel 4.1', linker wajib mengunci ke Tabel 4.1.
    """
    linker = CellLinker()
    claim_penetrate = {
        "claim_id": "C_5_2",
        "page": 5,
        "text": "Berdasarkan Tabel 4.1, nilai minimum variabel likuiditas adalah sebesar 0,17.",
        "scope_table_id": "Tabel_4_2"  # Zona aktif saat ini adalah Tabel 4.2
    }

    findings = linker.link_claim_to_table(claim_penetrate, sample_tables)
    assert len(findings) > 0, "Klaim rujukan eksplisit Tabel 4.1 harus tertaut"
    for f in findings:
        tbl_id = f.get("table_evidence", {}).get("table_id")
        assert tbl_id == "Tabel_4_1", f"Klaim gagal menembus zona scope, tertaut ke {tbl_id}"
        assert f.get("verdict") == "PASS_EXACT_MATCH"


def test_nonexistent_table_reference_abstains(sample_tables):
    """
    3. Rujukan eksplisit ke tabel yang tidak ada ('Tabel 4.99') wajib abstain:
    Linker tidak boleh fallback ke Tabel 4.1 atau Tabel 4.2, melainkan harus
    mengosongkan eval_tables dan mengembalikan hasil kosong (abstain).
    """
    linker = CellLinker()
    claim_nonexistent = {
        "claim_id": "C_5_3",
        "page": 5,
        "text": "Menurut Tabel 4.99, nilai likuiditas perusahaan tercatat sebesar 99,99.",
        "scope_table_id": "Tabel_4_1"
    }

    findings = linker.link_claim_to_table(claim_nonexistent, sample_tables)
    # Wajib abstain: findings kosong, tidak boleh menghasilkan verdict fatal palsu terhadap Tabel 4.1/4.2
    assert len(findings) == 0, f"Linker harus abstain untuk tabel fiktif 4.99, tapi menghasilkan {findings}"
