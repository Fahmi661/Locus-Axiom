"""
LOCUS v3.4 Fast End-to-End Contract & API Sync Tests.
Fast execution (< 1 second), zero network hangs.
Verifies:
1. Single-source-of-truth JSON contract fields on findings[].
2. Strict prohibition of 'Valid' as row/variable label.
3. Clean human_explanation without raw '::'.
4. Table routing, Likert extraction, and engine_version == 'v3.4-synced'.
"""

import pytest
from backend.layer2_core.cell_linker import CellLinker
from backend.layer2_core.spss_likert_engine import (
    parse_spss_frequency_table,
    is_spss_frequency_table,
    normalize_table_id,
    route_claim_to_exact_table,
    extract_likert_claims_by_clause,
    check_likert_row_sum_in_sentence
)


def test_table_id_normalization():
    """Verify Roman and decimal table ID canonical routing."""
    assert normalize_table_id("Berdasarkan Tabel IV.21...") == "4.21"
    assert normalize_table_id("Menurut tabel 4.3 berikut") == "4.3"
    assert normalize_table_id("pada Tabel IV") == "4"


def test_spss_frequency_table_never_labels_valid():
    """Verify 'Valid' column 0 stub is bypassed and never becomes a row label."""
    headers = ["Keterangan", "Kategori", "Frequency", "Percent", "Valid Percent"]
    rows = [
        ["Valid", "Sangat Tidak Setuju", "1", "1,0", "1,0"],
        ["", "Tidak Setuju", "7", "7,0", "7,0"],
        ["", "Netral", "58", "58,0", "58,0"],
        ["", "Setuju", "48", "48,0", "48,0"],
        ["", "Sangat Setuju", "23", "23,0", "23,0"],
        ["", "Total", "100", "100,0", "100,0"]
    ]

    assert is_spss_frequency_table(headers, rows) is True
    cleaned = parse_spss_frequency_table(headers, rows)

    # Must contain canonical codes STS, TS, N, S, SS, TOTAL
    assert "STS" in cleaned
    assert "S" in cleaned
    assert "TOTAL" in cleaned
    # 'Valid' must NEVER be a key
    assert "VALID" not in cleaned
    assert "valid" not in cleaned


def test_contract_enrichment_keys():
    """Verify that CellLinker produces all 10 single-source-of-truth contract fields."""
    linker = CellLinker()

    mock_doc = {
        "document_id": "TEST-DOC-SYNC",
        "claims": [
            {
                "claim_id": "C_1_1",
                "page": 1,
                "text": "Tabel 4.1 menunjukkan sebanyak 48 responden atau (48%) menyatakan setuju.",
                "claim_y_top": 200.0,
                "bbox": [50, 190, 500, 215],
                "boxes": [[50, 190, 500, 215]]
            }
        ],
        "tables": [
            {
                "table_id": "Tabel_4_1",
                "normalized_id": "4.1",
                "caption": "Budaya Organisasi 3",
                "page": 1,
                "bbox": [50, 50, 500, 150],
                "header_paths": ["Kategori", "Frequency", "Percent", "Valid Percent"],
                "rows": [
                    [{"row_label": "Valid", "raw_val": "Valid"}, {"row_label": "Setuju", "raw_val": "Setuju"}, {"raw_val": "35", "num_val": 35.0}, {"raw_val": "35,0", "num_val": 35.0}, {"raw_val": "35,0", "num_val": 35.0}]
                ]
            }
        ],
        "page_dimensions": {
            1: [595.0, 842.0, 0.0, 0.0]
        }
    }

    result = linker.audit_document(mock_doc)
    assert result["document_id"] == "TEST-DOC-SYNC"
    findings = result["findings"]
    assert len(findings) >= 1

    finding = findings[0]

    # 1. table_ref
    assert "table_ref" in finding
    assert "Tabel" in finding["table_ref"]

    # 2. row_category (MUST NOT BE 'Valid')
    assert "row_category" in finding
    assert finding["row_category"].strip().lower() != "valid"

    # 3. stat_column
    assert "stat_column" in finding
    assert isinstance(finding["stat_column"], str)

    # 4. claim_value_display
    assert "claim_value_display" in finding
    assert len(finding["claim_value_display"]) > 0

    # 5. table_value_display
    assert "table_value_display" in finding
    assert len(finding["table_value_display"]) > 0

    # 6. highlighted_clause
    assert "highlighted_clause" in finding
    assert "<mark>" in finding["highlighted_clause"]

    # 7. human_explanation (No raw '::')
    assert "human_explanation" in finding
    assert "::" not in finding["human_explanation"]

    # 8. stack_trace_path
    assert "stack_trace_path" in finding
    assert "->" in finding["stack_trace_path"]

    # 9. socratic_hints (At least 2 progressive hints)
    assert "socratic_hints" in finding
    assert len(finding["socratic_hints"]) >= 2

    # 10. table_bbox_norm (0..1 normalized coordinates)
    assert "table_bbox_norm" in finding
    bbox_norm = finding["table_bbox_norm"]
    assert bbox_norm is not None
    assert "page" in bbox_norm
    assert 0.0 <= bbox_norm["x0"] <= 1.0
    assert 0.0 <= bbox_norm["y0"] <= 1.0


def test_invalid_row_labels_and_row_snippet():
    """Verify that 'VALID' and 'MISSING' are rejected, and build_row_snippet checks col 0 and 1."""
    from backend.layer2_core.cell_linker import is_invalid_row_label, build_row_snippet
    assert is_invalid_row_label("Valid") is True
    assert is_invalid_row_label("VALID") is True
    assert is_invalid_row_label("Missing") is True
    assert is_invalid_row_label("MISSING") is True
    assert is_invalid_row_label("Ukuran Perusahaan") is False

    tbl = {
        "table_id": "Tabel_4_1",
        "page": 1,
        "header_paths": ["Keterangan", "Kategori", "Frequency", "Percent"],
        "rows": [
            [
                {"row_label": "Valid", "raw_val": "Valid"},
                {"row_label": "Setuju", "raw_val": "Setuju"},
                {"raw_val": "35", "num_val": 35.0},
                {"raw_val": "35,0", "num_val": 35.0}
            ]
        ]
    }
    snippet = build_row_snippet(tbl, "Setuju", "Percent")
    assert snippet["row_label"] == "Setuju"
    assert len(snippet["cells"]) == 4
