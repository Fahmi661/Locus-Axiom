"""
Regression test suite for LOCUS v3.5.2.
Guarantees KeyError: 'row' immunity in stitch_cross_page_tables() and uniform cell normalization across OCR fallback and vector extractors.
"""

import pytest
from backend.layer1_perception.table_geometry import TableGeometryExtractor
from backend.layer1_perception.ocr_fallback import OcrTableFallback


def test_stitch_cross_page_tables_without_row_key():
    """Verifies that cross-page stitching never raises KeyError: 'row' even if OCR cells lack 'row'."""
    tbl1 = {
        "table_id": "Tabel_1",
        "page": 1,
        "num_cols": 2,
        "num_rows": 2,
        "bbox": [50.0, 100.0, 450.0, 500.0],
        "rows": [
            [
                {"row": 1, "col": 1, "text": "Model", "raw_val": "Model", "bbox": [50, 100, 200, 120]},
                {"row": 1, "col": 2, "text": "RMSE", "raw_val": "RMSE", "bbox": [200, 100, 450, 120]}
            ],
            [
                {"row": 2, "col": 1, "text": "Linear", "raw_val": "Linear", "bbox": [50, 120, 200, 140]},
                {"row": 2, "col": 2, "text": "2.45", "raw_val": "2.45", "bbox": [200, 120, 450, 140]}
            ]
        ]
    }

    # tbl2 on page 2 has identical column count and matching horizontal bbox (dx <= 8),
    # but its cells originate from OCR without the 'row' key
    tbl2_ocr = {
        "table_id": "Tabel_OCR_2_1",
        "page": 2,
        "num_cols": 2,
        "num_rows": 2,
        "bbox": [52.0, 50.0, 452.0, 300.0],
        "rows": [
            [
                {"row_idx": 0, "col_idx": 0, "text": "XGBoost", "raw_val": "XGBoost", "bbox": [52, 50, 200, 70]},
                {"row_idx": 0, "col_idx": 1, "text": "1.20", "raw_val": "1.20", "bbox": [200, 50, 452, 70]}
            ],
            [
                # Raw dict with only bbox and text, missing both row and col keys
                {"bbox": [52, 70, 200, 90], "text": "CatBoost"},
                # Raw string cell
                "0.98"
            ]
        ]
    }

    stitched = TableGeometryExtractor.stitch_cross_page_tables([tbl1, tbl2_ocr])
    assert len(stitched) == 1, "Expected tables to be stitched into 1 merged table"
    merged = stitched[0]
    assert merged["is_cross_page"] is True
    assert merged["num_rows"] == 4

    # Check cell keys across all stitched rows
    for r_idx, row in enumerate(merged["rows"]):
        for c_idx, cell in enumerate(row):
            assert isinstance(cell, dict), f"Cell must be a dict, got {type(cell)}"
            assert "row" in cell, f"Cell at ({r_idx}, {c_idx}) missing 'row': {cell}"
            assert "col" in cell, f"Cell at ({r_idx}, {c_idx}) missing 'col': {cell}"
            assert "text" in cell, f"Cell at ({r_idx}, {c_idx}) missing 'text': {cell}"
            assert "bbox" in cell, f"Cell at ({r_idx}, {c_idx}) missing 'bbox': {cell}"

    # Verify offset was applied correctly to the stitched second-page rows
    assert merged["rows"][2][0]["row"] == 3
    assert merged["rows"][3][0]["row"] == 4


def test_ocr_fallback_normalize_cells():
    """Verifies that OcrTableFallback.normalize_cells creates complete dicts from arbitrary inputs."""
    raw_mixed_rows = [
        ["Header A", "Header B"],
        [{"text": "Data 1", "bbox": [10, 10, 50, 30]}, {"raw_val": "Data 2"}],
        [{"bbox": [10, 30, 50, 50], "width": 40, "height": 20}, 42]
    ]

    normalized = OcrTableFallback.normalize_cells(raw_mixed_rows)
    assert len(normalized) == 3

    for r_idx, row in enumerate(normalized):
        assert len(row) == 2
        for c_idx, cell in enumerate(row):
            assert "row" in cell
            assert "col" in cell
            assert "text" in cell
            assert "bbox" in cell
            assert cell["row"] == r_idx + 1
            assert cell["col"] == c_idx + 1
