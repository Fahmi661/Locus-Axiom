"""
Precision & X-Ray Verification Test Suite for KRITERON.
Covers unified PDF coordinate frame, CropBox single-compensation, OCR _px_to_pt,
strict cell-word matching, multi-tier SPSS headers, leading-dot/PUEBI disambiguation,
multi-number clause binding, floating table resolution, and API payload schema.
"""

import os
import tempfile
import numpy as np
import pytest
import pypdfium2 as pdfium


def _build_pdf_with_cropbox(
    mediabox=(0, 0, 612, 792),
    cropbox=(50, 100, 550, 700),
    rot=0,
    content_stream="BT /F1 12 Tf 100 600 Td (Rata-rata nilai sebesar 12,34 pada sampel.) Tj ET",
):
    """Builds a minimal valid PDF binary with explicit MediaBox, CropBox, and /Rotate."""
    objs = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        (
            f"3 0 obj << /Type /Page /Parent 2 0 R "
            f"/MediaBox [{' '.join(map(str, mediabox))}] "
            f"/CropBox [{' '.join(map(str, cropbox))}] "
            f"/Rotate {rot} "
            f"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        ).encode(),
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    stream = content_stream.encode("latin-1")
    objs.append(
        f"5 0 obj << /Length {len(stream)} >> stream\n".encode()
        + stream
        + b"\nendstream endobj\n"
    )
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


# =====================================================================
# C1 / C2 / C3: Coordinate Frame, CropBox, OCR _px_to_pt, No Fake Boxes
# =====================================================================

def test_render_scale_and_ocr_px_to_pt():
    """OCR pixel-to-point conversion uses RENDER_SCALE=1.5 and rejects zero/invalid boxes."""
    from backend.layer1_perception.pdf_reader import FastPdfReader, RENDER_SCALE
    from backend.layer1_perception.ocr_fallback import OcrTableFallback

    assert RENDER_SCALE == 1.5

    # Crop image located at pixel origin (150, 300) in rendered page (= (100pt, 200pt))
    # Cell inside crop at pixels [30, 15, 120, 45] -> global px [180, 315, 270, 345] -> pt [120, 210, 180, 230]
    pt_rect = FastPdfReader._px_to_pt([30, 15, 120, 45], crop_origin_px=(150, 300), scale=RENDER_SCALE)
    assert pt_rect == [120.0, 210.0, 180.0, 230.0]

    # Zero-area and degenerate boxes must return None, never [0, 0, 0, 0]
    assert FastPdfReader._px_to_pt([0, 0, 0, 0], crop_origin_px=(0, 0)) is None
    assert FastPdfReader._px_to_pt([10, 10, 10, 30], crop_origin_px=(0, 0)) is None
    assert FastPdfReader._px_to_pt([50, 20, 40, 30], crop_origin_px=(0, 0)) is None
    assert FastPdfReader._px_to_pt(None) is None

    # OcrTableFallback.normalize_cells must set missing/zero bboxes to None, never [0,0,0,0]
    normalized = OcrTableFallback.normalize_cells([
        ["Header A", {"text": "0.45", "bbox": [0, 0, 0, 0]}],
        [{"text": "Row 1", "bbox": [10, 20, 80, 40]}, "12.34"],
    ])
    assert normalized[0][0]["bbox"] is None
    assert normalized[0][1]["bbox"] is None
    assert normalized[1][0]["bbox"] == [10, 20, 80, 40]
    assert normalized[1][1]["bbox"] is None


def test_ocr_fallback_in_process_pdf_emits_normalized_point_rects(monkeypatch):
    """OCR fallback cells must all lie inside the table image region in PDF points, never [0,0,0,0]."""
    from unittest.mock import patch
    from PIL import Image
    from backend.layer1_perception.pdf_reader import FastPdfReader, RENDER_SCALE
    from backend.layer1_perception.ocr_fallback import OcrTableFallback

    # Build a 1-page PDF with CropBox [50, 100, 550, 700] and no vector tables
    pdf_bytes = _build_pdf_with_cropbox(
        mediabox=(0, 0, 612, 792),
        cropbox=(50, 100, 550, 700),
        rot=0,
        content_stream="BT /F1 12 Tf 100 600 Td (Narasi di atas gambar tabel.) Tj ET",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "scan.pdf")
        out_dir = os.path.join(tmpdir, "pages")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        # Fake an embedded image on page 1 at raw pdfplumber coords [100, 200, 400, 400]
        # After CropBox (50, 92) compensation, visible image region is [50.0, 108.0, 350.0, 308.0]
        fake_img_meta = {"x0": 100.0, "top": 200.0, "x1": 400.0, "bottom": 400.0, "width": 300.0, "height": 200.0}
        fake_ocr_res = {
            "source": "MOCK_OCR",
            "rows": [
                [{"text": "Var", "bbox": [15, 15, 90, 45]}, {"text": "Mean", "bbox": [105, 15, 210, 45]}],
                ["X1", {"text": "0.42", "bbox": [105, 60, 210, 90]}],
            ],
        }

        import pdfplumber
        orig_open = pdfplumber.open

        class _PageProxy:
            def __init__(self, p):
                self._p = p
                self.images = [fake_img_meta]
            def __getattr__(self, item):
                return getattr(self._p, item)

        class _PdfProxy:
            def __init__(self, pdf):
                self._pdf = pdf
                self.pages = [_PageProxy(p) for p in pdf.pages]
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return self._pdf.__exit__(*args)

        def _patched_open(path, *args, **kwargs):
            return _PdfProxy(orig_open(path, *args, **kwargs))

        monkeypatch.setattr(pdfplumber, "open", _patched_open)
        monkeypatch.setattr(OcrTableFallback, "extract_table_from_image", classmethod(lambda cls, arr: fake_ocr_res))

        doc_graph = FastPdfReader.process_pdf(pdf_path, output_images_dir=out_dir)
        assert len(doc_graph["tables"]) == 1
        tbl = doc_graph["tables"][0]
        tb = tbl["bbox"]
        assert tb == [50.0, 108.0, 350.0, 308.0]

        for row in tbl["rows"]:
            for cell in row:
                b = cell["bbox"]
                assert b is not None and b != [0, 0, 0, 0]
                assert b[0] >= tb[0] - 0.1 and b[1] >= tb[1] - 0.1
                assert b[2] <= tb[2] + 0.1 and b[3] <= tb[3] + 0.1
                assert b[2] > b[0] and b[3] > b[1]
                assert cell["cell_rect"] == b

        # String cell "X1" had no pixel bbox -> falls back to image region with bbox_approx=True
        c_str = tbl["rows"][1][0]
        assert c_str["bbox"] == tb
        assert c_str["bbox_approx"] is True

        # Exact pixel cell [105, 60, 210, 90] at RENDER_SCALE=1.5 offset from (50*1.5=75, 108*1.5=162)
        # -> [(75+105)/1.5, (162+60)/1.5, (75+210)/1.5, (162+90)/1.5] = [120.0, 148.0, 190.0, 168.0]
        c_num = tbl["rows"][1][1]
        assert c_num["bbox_approx"] is False
        assert c_num["bbox"] == [120.0, 148.0, 190.0, 168.0]


def test_cropbox_single_compensation_matches_rendered_ink():
    """
    A PDF with non-zero CropBox origin [50, 100, 550, 700] inside MediaBox [0, 0, 612, 792]
    must emit normalized rects matching pypdfium2 rendered positions within 0.5pt (on x0/x1)
    with compensation applied exactly once.
    """
    from backend.layer1_perception.pdf_reader import FastPdfReader, RENDER_SCALE

    pdf_bytes = _build_pdf_with_cropbox(
        mediabox=(0, 0, 612, 792),
        cropbox=(50, 100, 550, 700),
        rot=0,
        content_stream="BT /F1 12 Tf 100 600 Td (Rata-rata nilai sebesar 12,34 pada sampel.) Tj ET",
    )
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(pdf_bytes)
        pdf_path = tf.name

    try:
        # Render with pypdfium2 to measure actual visible page size and ink position
        doc = pdfium.PdfDocument(pdf_path)
        page_i = doc[0]
        img = page_i.render(scale=RENDER_SCALE).to_pil().convert("L")
        arr = np.array(img)
        ys, xs = np.where(arr < 200)
        ink_x0 = xs.min() / RENDER_SCALE
        ink_y0 = ys.min() / RENDER_SCALE
        ink_x1 = xs.max() / RENDER_SCALE
        ink_y1 = ys.max() / RENDER_SCALE
        doc.close()

        doc_graph = FastPdfReader.process_pdf(pdf_path)
        assert doc_graph["render_scale"] == RENDER_SCALE
        dims = doc_graph["page_dimensions"][1]
        # Visible CropBox size is 500 x 600 pt, and origin offsets already compensated -> 0.0, 0.0
        assert abs(dims[0] - 500.0) <= 0.5
        assert abs(dims[1] - 600.0) <= 0.5
        assert dims[2] == 0.0 and dims[3] == 0.0

        assert len(doc_graph["claims"]) == 1
        claim = doc_graph["claims"][0]
        bbox = claim["bbox"]
        # Exact analytical position: x0 = 100 - 50 = 50.0, top = (792 - 600 - ascent) - (792 - 700) ~ 90.5
        # Must match expected CropBox-compensated coordinates within 0.5pt (not shifted by +50 or +92!)
        assert abs(bbox[0] - 50.0) <= 0.5, f"x0={bbox[0]} should be ~50.0 (ink_x0={ink_x0:.2f})"
        assert abs(bbox[1] - 90.5) <= 0.5, f"y0={bbox[1]} should be ~90.5 (ink_y0={ink_y0:.2f})"
        assert abs(bbox[0] - ink_x0) <= 1.5
        assert abs(bbox[1] - ink_y0) <= 2.0
        assert abs(bbox[2] - ink_x1) <= 2.0
        assert abs(bbox[3] - ink_y1) <= 3.0
    finally:
        os.unlink(pdf_path)


def test_no_hardcoded_fallback_rects_on_missing_dims():
    """build_table_bbox_norm returns None when dims are missing; CellLinker never emits fake fallback rects."""
    from backend.layer2_core.cell_linker import build_table_bbox_norm, CellLinker

    tbl = {"table_id": "T1", "page": 1, "bbox": [50, 100, 400, 250]}
    assert build_table_bbox_norm(tbl, None) is None
    assert build_table_bbox_norm(tbl, {}) is None
    assert build_table_bbox_norm(None, {1: [595.0, 842.0, 0.0, 0.0]}) is None

    # When page_dimensions is missing in audit_document, findings must NOT get fake {0.05,0.1,0.95,0.4} or [72,100,500,120]
    linker = CellLinker()
    doc_graph = {
        "document_id": "NO-DIMS-TEST",
        "claims": [
            {
                "claim_id": "C_1",
                "page": 1,
                "text": "Berdasarkan Tabel 4.1, data berdistribusi normal karena nilai Sig. Kolmogorov-Smirnov sebesar 0,012 < 0,05.",
            }
        ],
        "tables": [
            {
                "table_id": "Tabel_4_1",
                "normalized_id": "4.1",
                "page": 1,
                "bbox": [50.0, 100.0, 400.0, 200.0],
                "header_paths": ["Uji Normalitas", "Sig."],
                "rows": [
                    [
                        {"row": 1, "col": 1, "row_label": "Kolmogorov-Smirnov", "raw_val": "Kolmogorov-Smirnov", "header_path": "Uji Normalitas", "num_val": None, "bbox": [50, 120, 250, 140]},
                        {"row": 1, "col": 2, "row_label": "Kolmogorov-Smirnov", "raw_val": "0,012", "header_path": "Sig.", "num_val": 0.012, "bbox": [250, 120, 400, 140]},
                    ]
                ],
            }
        ],
        "page_dimensions": {},
    }
    res = linker.audit_document(doc_graph)
    assert len(res["findings"]) >= 1
    f = res["findings"][0]
    assert f["table_bbox_norm"] is None
    assert f["claim_source"]["bbox"] is None
    assert f["claim_source"]["bbox"] != [72, 100, 500, 120]
    assert f["claim_source"]["bbox"] != [31.2, 289.9, 564.1, 316.9]


# =====================================================================
# C5 / C6 / 2.3: Strict Cell-Word Matching, Multi-Tier SPSS Headers, 3-Line Tables
# =====================================================================

def test_adjacent_cells_zero_never_lands_in_neighbor():
    """
    C5: Two adjacent cells with '2,67' and '0' (plus a neighboring cell containing '0' inside '10,4'):
    the bbox of '0' must stay strictly inside its own cell_box and never match a word in the neighbor.
    """
    from backend.layer1_perception.table_geometry import TableGeometryExtractor

    class _MockRow:
        def __init__(self, cells):
            self.cells = cells

    class _MockTable:
        bbox = (50.0, 100.0, 350.0, 160.0)
        rows = [
            _MockRow([(50.0, 100.0, 150.0, 130.0), (150.0, 100.0, 250.0, 130.0), (250.0, 100.0, 350.0, 130.0)]),
            _MockRow([(50.0, 130.0, 150.0, 160.0), (150.0, 130.0, 250.0, 160.0), (250.0, 130.0, 350.0, 160.0)]),
        ]
        def extract(self):
            return [
                ["Variabel", "Mean", "Min"],
                ["X1", "2,67", "0"],
            ]

    class _MockPage:
        lines = []
        width = 595.0
        height = 842.0
        def find_tables(self):
            return [_MockTable()]
        def extract_words(self):
            # Notice '2,670' sits near the right border of col 1 (x=247..249.5, within 4pt of col 2!)
            # and '0' sits cleanly inside col 2 (x=295..302).
            # Under the old ±4pt + substring `w["text"] in raw_val` / `raw_val in w["text"]`,
            # cell '0' (col 2: 250..350) matched '2,670' in col 1 because '0' in '2,670' and 248 >= 250-4!
            return [
                {"text": "Variabel", "x0": 60.0, "x1": 110.0, "top": 108.0, "bottom": 120.0},
                {"text": "Mean", "x0": 180.0, "x1": 210.0, "top": 108.0, "bottom": 120.0},
                {"text": "Min", "x0": 285.0, "x1": 310.0, "top": 108.0, "bottom": 120.0},
                {"text": "X1", "x0": 60.0, "x1": 75.0, "top": 138.0, "bottom": 150.0},
                {"text": "2,670", "x0": 236.0, "x1": 258.0, "top": 138.0, "bottom": 150.0},  # center=247.0 (in col 1!)
                {"text": "0", "x0": 295.0, "x1": 302.0, "top": 138.0, "bottom": 150.0},      # center=298.5 (in col 2!)
            ]

    tables = TableGeometryExtractor.extract_tables_from_pdfplumber_page(_MockPage(), 1)
    assert len(tables) == 1
    row0 = tables[0]["rows"][0]
    cell_mean = row0[1]
    cell_zero = row0[2]

    # Cell '0' bbox must lie strictly within col 2 [250, 350] and around word '0' (295..302)
    assert cell_zero["bbox"][0] >= 250.0, f"Cell '0' leaked into neighbor cell: {cell_zero['bbox']}"
    assert cell_zero["bbox"][2] <= 350.0
    assert cell_zero["bbox"][0] >= 290.0 and cell_zero["bbox"][2] <= 306.0
    assert cell_zero["cell_rect"] == cell_zero["bbox"]
    assert cell_zero["bbox_approx"] is False

    # Cell '2,67' numeric equality matches '2,670' inside col 1 [150, 250]
    assert cell_mean["bbox"][0] >= 150.0 and cell_mean["bbox"][2] <= 260.0


def test_multitier_spss_coefficients_header_unmerging():
    """2.3: Deterministic hierarchical unmerging of standard 2-tier SPSS Coefficients headers."""
    from backend.layer1_perception.table_geometry import TableGeometryExtractor

    # Standard SPSS 2-tier Coefficients table (Layout A)
    raw_a = [
        ["Model", "Unstandardized Coefficients", None, "Standardized Coefficients", "t", "Sig."],
        [None, "B", "Std. Error", "Beta", None, None],
        ["(Constant)", "1.245", ".312", "", "3.990", ".000"],
        ["Likuiditas", ".418", ".105", ".352", "3.981", ".000"],
    ]
    headers_a, start_a = TableGeometryExtractor.flatten_multitier_headers(raw_a)
    assert start_a == 2
    assert headers_a == [
        "Model",
        "Unstandardized Coefficients :: B",
        "Unstandardized Coefficients :: Std. Error",
        "Standardized Coefficients :: Beta",
        "t",
        "Sig.",
    ]

    # SPSS 2-tier Coefficients table where t and Sig. appear on row 1 under None in row 0 (Layout B)
    raw_b = [
        ["Model", None, "Unstandardized Coefficients", None, "Standardized Coefficients", None, None],
        [None, None, "B", "Std. Error", "Beta", "t", "Sig."],
        ["1", "Likuiditas", ".418", ".105", ".352", "3.981", ".000"],
    ]
    headers_b, start_b = TableGeometryExtractor.flatten_multitier_headers(raw_b)
    assert start_b == 2
    assert headers_b[2] == "Unstandardized Coefficients :: B"
    assert headers_b[3] == "Unstandardized Coefficients :: Std. Error"
    assert headers_b[4] == "Standardized Coefficients :: Beta"
    assert headers_b[5] == "t"
    assert headers_b[6] == "Sig."


def test_3line_apa_table_keeps_negative_values_separate():
    """2.3: Borderless 3-line APA table never merges negative values (-0,412) into adjacent columns."""
    from backend.layer1_perception.table_geometry import TableGeometryExtractor

    class _MockApaPage:
        width = 595.0
        height = 842.0
        lines = [
            {"x0": 50.0, "x1": 450.0, "top": 100.0, "bottom": 100.5},
            {"x0": 50.0, "x1": 450.0, "top": 122.0, "bottom": 122.5},
            {"x0": 50.0, "x1": 450.0, "top": 170.0, "bottom": 170.5},
        ]
        def extract_words(self):
            return [
                # Header line
                {"text": "Variabel", "x0": 55.0, "x1": 105.0, "top": 105.0, "bottom": 117.0},
                {"text": "B", "x0": 210.0, "x1": 220.0, "top": 105.0, "bottom": 117.0},
                {"text": "Beta", "x0": 255.0, "x1": 280.0, "top": 105.0, "bottom": 117.0},
                {"text": "t", "x0": 325.0, "x1": 332.0, "top": 105.0, "bottom": 117.0},
                {"text": "Sig.", "x0": 375.0, "x1": 398.0, "top": 105.0, "bottom": 117.0},
                # Data line 1 (notice only 14pt gap between 0,312 and -0,412 — previously merged by gap=25!)
                {"text": "Ukuran", "x0": 55.0, "x1": 95.0, "top": 130.0, "bottom": 142.0},
                {"text": "Perusahaan", "x0": 99.0, "x1": 160.0, "top": 130.0, "bottom": 142.0},
                {"text": "0,312", "x0": 200.0, "x1": 230.0, "top": 130.0, "bottom": 142.0},
                {"text": "-0,412", "x0": 244.0, "x1": 280.0, "top": 130.0, "bottom": 142.0},
                {"text": "-2,145", "x0": 310.0, "x1": 346.0, "top": 130.0, "bottom": 142.0},
                {"text": "0,034", "x0": 370.0, "x1": 400.0, "top": 130.0, "bottom": 142.0},
            ]

    tbl = TableGeometryExtractor.extract_3line_table(_MockApaPage(), 1)
    assert tbl is not None
    assert tbl["num_cols"] == 5, f"Expected 5 columns, got {tbl['num_cols']}: {tbl['rows']}"
    vals = [c["raw_val"] for c in tbl["rows"][0]]
    assert vals == ["Ukuran Perusahaan", "0,312", "-0,412", "-2,145", "0,034"]
    assert abs(tbl["rows"][0][2]["num_val"] - (-0.412)) < 1e-6


def test_missing_cell_box_uses_word_clustering_and_marks_uniform_approx():
    """C6: Missing cell_box derives uneven column bounds from words; uniform fallback marks bbox_approx=True."""
    from backend.layer1_perception.table_geometry import TableGeometryExtractor

    class _MockTableNoCells:
        bbox = (50.0, 100.0, 450.0, 160.0)
        rows = []  # pdfplumber cell_box missing
        def extract(self):
            return [
                ["Nama Variabel Panjang", "N", "Mean"],
                ["Profitabilitas Perusahaan", "96", "12,45"],
            ]

    class _MockPageUneven:
        lines = []
        width = 595.0
        height = 842.0
        def find_tables(self):
            return [_MockTableNoCells()]
        def extract_words(self):
            # Very wide col 0 (55..290), narrow col 1 (320..335), col 2 (390..430)
            return [
                {"text": "Nama", "x0": 55.0, "x1": 90.0, "top": 108.0, "bottom": 120.0},
                {"text": "Variabel", "x0": 94.0, "x1": 145.0, "top": 108.0, "bottom": 120.0},
                {"text": "Panjang", "x0": 149.0, "x1": 200.0, "top": 108.0, "bottom": 120.0},
                {"text": "N", "x0": 324.0, "x1": 333.0, "top": 108.0, "bottom": 120.0},
                {"text": "Mean", "x0": 395.0, "x1": 425.0, "top": 108.0, "bottom": 120.0},
                {"text": "Profitabilitas", "x0": 55.0, "x1": 140.0, "top": 136.0, "bottom": 148.0},
                {"text": "Perusahaan", "x0": 144.0, "x1": 225.0, "top": 136.0, "bottom": 148.0},
                {"text": "96", "x0": 322.0, "x1": 336.0, "top": 136.0, "bottom": 148.0},
                {"text": "12,45", "x0": 392.0, "x1": 426.0, "top": 136.0, "bottom": 148.0},
            ]

    tables = TableGeometryExtractor.extract_tables_from_pdfplumber_page(_MockPageUneven(), 1)
    assert len(tables) == 1
    row0 = tables[0]["rows"][0]
    # Uniform grid would put col 1 at [183.3..316.7], completely missing word '96' at [322..336]!
    # Clustered bounds must pinpoint '96' accurately at [322.0, 136.0, 336.0, 148.0].
    assert row0[1]["bbox"] == [322.0, 136.0, 336.0, 148.0]
    assert row0[2]["bbox"] == [392.0, 136.0, 426.0, 148.0]

    # When NO words exist at all, uniform grid last-resort MUST flag bbox_approx=True
    class _MockPageEmptyWords(_MockPageUneven):
        def extract_words(self):
            return []

    tables_empty = TableGeometryExtractor.extract_tables_from_pdfplumber_page(_MockPageEmptyWords(), 1)
    assert tables_empty[0]["rows"][0][1]["bbox_approx"] is True


# =====================================================================
# 2.4 / 2.5 / C7: SPSS vs PUEBI Disambiguation, Line Grouping, value_rect
# =====================================================================

def test_spss_leading_dot_and_correlation_1000_disambiguation():
    """
    2.4: Leading-dot SPSS decimals (.000, .042, -.318, −.318) normalize cleanly, and
    3-decimal statistical values like 1.000 / 0.000 inside correlation/reliability/sig
    tables parse as decimal floats (1.0, 0.0) even under ID_PUEBI locale.
    """
    from backend.layer1_perception.number_normalizer import NumberNormalizer

    p_zero = NumberNormalizer.parse_numeric(".000")
    assert p_zero is not None and p_zero["float_val"] == 0.0 and p_zero["decimals"] == 3

    p_pos = NumberNormalizer.parse_numeric(".042")
    assert p_pos is not None and abs(p_pos["float_val"] - 0.042) < 1e-9 and p_pos["decimals"] == 3

    p_neg = NumberNormalizer.parse_numeric("-.318")
    assert p_neg is not None and abs(p_neg["float_val"] - (-0.318)) < 1e-9 and p_neg["decimals"] == 3

    p_unicode_neg = NumberNormalizer.parse_numeric("\u2212.318")
    assert p_unicode_neg is not None and abs(p_unicode_neg["float_val"] - (-0.318)) < 1e-9

    # Correlation / Reliability / Sig table: 1.000 and 0.000 must NOT become 1000 under ID_PUEBI!
    p_corr = NumberNormalizer.parse_numeric("1.000", column_locale="ID_PUEBI", header_context="Pearson Correlation")
    assert p_corr is not None and p_corr["float_val"] == 1.0 and p_corr["decimals"] == 3

    p_sig = NumberNormalizer.parse_numeric("0.000", column_locale="ID_PUEBI", header_context="Sig. (2-tailed)")
    assert p_sig is not None and p_sig["float_val"] == 0.0 and p_sig["decimals"] == 3

    p_rel = NumberNormalizer.parse_numeric("1.000", column_locale="ID_PUEBI", table_context="Reliability Statistics Cronbach Alpha")
    assert p_rel is not None and p_rel["float_val"] == 1.0

    # Non-statistical currency/count column under ID_PUEBI keeps thousand separator behavior
    p_rp = NumberNormalizer.parse_numeric("1.000", column_locale="ID_PUEBI", header_context="Harga (Rp)")
    assert p_rp is not None and p_rp["float_val"] == 1000.0


def test_two_line_claim_has_two_rects_and_value_rect_inside():
    """
    C7 / 2.5: A two-line narrative claim emits 2 line-level claim_rects, compact tok_boxes,
    and value_rect locating the exact numeric token inside one of the claim_rects.
    Also verifies superscript/mixed-font tokens stay grouped on the right visual line.
    """
    from backend.layer1_perception.pdf_reader import FastPdfReader
    from backend.layer2_core.cell_linker import find_value_rect_in_claim

    # Two lines of narrative text (y=600 and y=582 in PDF bottom-up -> top ~ 90.5 and 108.5 in CropBox)
    stream = (
        "BT "
        "/F1 12 Tf 100 600 Td (Berdasarkan Tabel 4.1 variabel Likuiditas memiliki) Tj "
        "0 -18 Td (nilai rata-rata sebesar 1,4831 pada sampel ini.) Tj "
        "ET"
    )
    pdf_bytes = _build_pdf_with_cropbox(
        mediabox=(0, 0, 612, 792),
        cropbox=(50, 100, 550, 700),
        rot=0,
        content_stream=stream,
    )
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(pdf_bytes)
        pdf_path = tf.name

    try:
        doc_graph = FastPdfReader.process_pdf(pdf_path)
        assert len(doc_graph["claims"]) == 1
        claim = doc_graph["claims"][0]
        rects = claim.get("claim_rects")
        assert rects is not None and len(rects) == 2, f"Expected 2 line rects, got {rects}"
        assert claim["boxes"] == rects
        assert "tok_boxes" in claim and len(claim["tok_boxes"]) >= 10

        val_rect = find_value_rect_in_claim(claim, "1,4831")
        assert val_rect is not None, f"Failed to locate value_rect in tok_boxes: {claim['tok_boxes']}"
        # value_rect must lie inside the second line rect (and be narrower than the full line)
        line2 = rects[1]
        assert val_rect[0] >= line2[0] - 0.5 and val_rect[2] <= line2[2] + 0.5
        assert val_rect[1] >= line2[1] - 0.5 and val_rect[3] <= line2[3] + 0.5
        assert (val_rect[2] - val_rect[0]) < (line2[2] - line2[0]) * 0.5
    finally:
        os.unlink(pdf_path)


# =====================================================================
# 2.6: Compound Clause Binding, Floating Tables, Likert Isolation, API Schema
# =====================================================================

def test_compound_sentence_local_token_binding():
    """
    2.6: Compound sentence with multiple numeric claims and comparison operators:
    'Variabel Likuiditas memiliki t hitung 2,415 > t tabel 1,984 dengan Sig. 0,018 < 0,05.'
    binds 2.415 strictly to STAT_TEST and 0.018 strictly to P_VALUE, and verifies
    accurately against a multi-tier SPSS Coefficients table.
    """
    from src.core.quad_tuple_verifier import (
        extract_quad_tuples_from_sentence,
        verify_quad_tuple_against_table,
    )

    sent = "Variabel Likuiditas memiliki t hitung 2,415 > t tabel 1,984 dengan Sig. 0,018 < 0,05."
    headers = [
        "Model",
        "Unstandardized Coefficients :: B",
        "Unstandardized Coefficients :: Std. Error",
        "Standardized Coefficients :: Beta",
        "Coefficients :: t",
        "Coefficients :: Sig.",
    ]
    rows = [
        ["(Constant)", "1.245", ".312", "", "3.990", ".000"],
        ["Likuiditas", ".418", ".105", ".352", "2.415", ".018"],
    ]

    quads = extract_quad_tuples_from_sentence(sent, candidate_table_variables=["Likuiditas"])
    stat_map = {q.stat_type: q for q in quads}
    assert "STAT_TEST" in stat_map and abs(stat_map["STAT_TEST"].numeric_value - 2.415) < 1e-6
    assert "P_VALUE" in stat_map and abs(stat_map["P_VALUE"].numeric_value - 0.018) < 1e-6
    # Critical thresholds (1.984 and 0.05) must NOT leak as empirical contradictions
    assert len(quads) == 2

    for q in quads:
        res = verify_quad_tuple_against_table(q, headers, rows)
        assert res.status == "VALID_EXACT", f"Expected VALID_EXACT for {q.stat_type}, got {res.status}: {res.explanation_id}"

    # Post-positioned labels in compound sentence must bind locally, never steal earlier left label
    sent_post = "Variabel Likuiditas memperoleh nilai 2,415 (t hitung) dan 0,018 (Sig.)."
    quads_post = extract_quad_tuples_from_sentence(sent_post, candidate_table_variables=["Likuiditas"])
    post_map = {q.stat_type: q for q in quads_post}
    assert "STAT_TEST" in post_map and abs(post_map["STAT_TEST"].numeric_value - 2.415) < 1e-6
    assert "P_VALUE" in post_map and abs(post_map["P_VALUE"].numeric_value - 0.018) < 1e-6


def test_cross_page_floating_table_resolution_and_discourse_reset():
    """
    2.6: Explicit reference to 'Tabel 4.3' pushed onto page+1 resolves across the page boundary,
    while Layout-Aware Discourse Reset prevents leakage across a major sub-chapter heading.
    """
    from backend.layer2_core.cell_linker import CellLinker

    t_4_2 = {
        "table_id": "Tabel_4_2",
        "normalized_id": "4.2",
        "page": 4,
        "y_bottom": 300.0,
        "bbox": [50.0, 100.0, 500.0, 300.0],
        "header_paths": ["Variabel", "Mean"],
        "rows": [
            [
                {"row": 1, "col": 1, "row_label": "Profitabilitas", "raw_val": "Profitabilitas", "header_path": "Variabel", "num_val": None, "bbox": [50, 140, 200, 160]},
                {"row": 1, "col": 2, "row_label": "Profitabilitas", "raw_val": "9,99", "header_path": "Mean", "num_val": 9.99, "bbox": [200, 140, 350, 160]},
            ]
        ],
    }
    # Floating Tabel 4.3 pushed by Word-to-PDF pagination to page 5
    t_4_3 = {
        "table_id": "Tabel_4_3",
        "normalized_id": "Tabel_4_3",
        "caption": "Tabel 4.3 Statistik Deskriptif Likuiditas",
        "page": 5,
        "y_bottom": 240.0,
        "bbox": [50.0, 80.0, 500.0, 240.0],
        "header_paths": ["Variabel", "Mean"],
        "rows": [
            [
                {"row": 1, "col": 1, "row_label": "Likuiditas", "raw_val": "Likuiditas", "header_path": "Variabel", "num_val": None, "bbox": [50, 120, 200, 140]},
                {"row": 1, "col": 2, "row_label": "Likuiditas", "raw_val": "1,48", "header_path": "Mean", "num_val": 1.48, "bbox": [200, 120, 350, 140]},
            ]
        ],
    }

    doc_graph = {
        "document_id": "FLOAT-TBL-TEST",
        "render_scale": 1.5,
        "tables": [t_4_2, t_4_3],
        "claims": [
            {
                "claim_id": "C_4_1",
                "page": 4,
                "claim_y_top": 620.0,
                "scope_table_id": "Tabel_4_2",
                "text": "Berdasarkan Tabel 4.3, variabel Likuiditas memiliki nilai rata-rata sebesar 1,48.",
                "bbox": [50.0, 620.0, 480.0, 634.0],
                "boxes": [[50.0, 620.0, 480.0, 634.0]],
                "claim_rects": [[50.0, 620.0, 480.0, 634.0]],
                "tok_boxes": [["1,48.", 440.0, 620.0, 475.0, 634.0]],
            }
        ],
        "page_dimensions": {4: [595.0, 842.0, 0.0, 0.0], 5: [595.0, 842.0, 0.0, 0.0]},
    }

    linker = CellLinker()
    bundle = linker.audit_document(doc_graph)
    findings = bundle["findings"]
    assert len(findings) >= 1
    f0 = findings[0]
    assert f0["verdict"] == "PASS_EXACT_MATCH"
    assert f0["table_evidence"]["table_id"] == "Tabel_4_3"
    assert f0["cell_page"] == 5
    assert f0["claim_source"]["page"] == 4


def test_likert_row_isolation_blocks_cumulative_and_valid_hijack():
    """
    2.6: In SPSS Likert tables, Cumulative Percent and Valid rows must never hijack
    category Percent matches or target cell highlighting even when values are identical.
    """
    from src.core.spss_likert_engine import parse_spss_frequency_table
    from backend.layer2_core.cell_linker import CellLinker

    headers = ["", "Kategori", "Frequency", "Percent", "Valid Percent", "Cumulative Percent"]
    rows = [
        ["Valid", "Sangat Tidak Setuju", "5", "5.0", "5.0", "5.0"],
        ["", "Tidak Setuju", "15", "15.0", "15.0", "20.0"],
        ["", "Setuju", "50", "50.0", "50.0", "70.0"],
        ["", "Sangat Setuju", "30", "30.0", "30.0", "100.0"],
        ["", "Total", "100", "100.0", "100.0", ""],
    ]
    cleaned = parse_spss_frequency_table(headers, rows)
    assert "VALID" not in cleaned
    # Row 'S' (Setuju) Percent is 50.0, NOT Cumulative Percent 70.0
    assert cleaned["S"].cells["PERCENT"] == 50.0
    assert cleaned["S"].cells["CUMULATIVE_PERCENT"] == 70.0

    # Claim wrongly quotes Cumulative Percent (70%) as Setuju Percent -> MUST detect contradiction
    # and highlight the 'Setuju' row's 'Percent' cell (NOT 'Sangat Tidak Setuju' and NOT 'Cumulative Percent')!
    tbl = {
        "table_id": "Tabel_4_5",
        "normalized_id": "4.5",
        "page": 1,
        "table_type": "SPSS_LIKERT_FREQ",
        "bbox": [50.0, 80.0, 500.0, 240.0],
        "header_paths": headers,
        "rows": [
            [
                {"row": r_i + 1, "col": c_i + 1, "row_label": r[1], "raw_val": val, "header_path": headers[c_i],
                 "num_val": float(val) if val.replace(".", "").isdigit() else None,
                 "bbox": [50.0 + c_i * 70, 100.0 + r_i * 22, 115.0 + c_i * 70, 118.0 + r_i * 22],
                 "cell_rect": [50.0 + c_i * 70, 100.0 + r_i * 22, 115.0 + c_i * 70, 118.0 + r_i * 22],
                 "bbox_approx": False}
                for c_i, val in enumerate(r)
            ]
            for r_i, r in enumerate(rows)
        ],
    }
    linker = CellLinker()
    findings = linker.link_claim_to_table(
        {
            "claim_id": "C_LIK_1",
            "page": 1,
            "claim_y_top": 300.0,
            "text": "Berdasarkan Tabel 4.5, sebanyak 70% responden menyatakan setuju.",
            "bbox": [50.0, 300.0, 400.0, 314.0],
            "boxes": [[50.0, 300.0, 400.0, 314.0]],
        },
        [tbl],
        page_dims={1: [595.0, 842.0, 0.0, 0.0]},
    )
    contra = [f for f in findings if f.get("verdict") == "DIRECT_CELL_CONTRADICTION"]
    assert len(contra) == 1
    ev_cells = contra[0]["table_evidence"]["cells"]
    assert len(ev_cells) == 1
    assert ev_cells[0]["row_label"] == "Setuju"
    assert ev_cells[0]["header_path"] == "Percent"


def test_audit_api_response_schema_has_new_and_legacy_fields():
    """
    2.6: /api/v1/audit response contract returns page_width_pt, page_height_pt, render_scale,
    claim_rects, claim_source.value_rect, cell_page, cell_page_width_pt, cell_page_height_pt,
    cell_rect, per-cell bbox_approx, while preserving all legacy fields.
    """
    from backend.layer1_perception.pdf_reader import FastPdfReader
    from backend.layer2_core.cell_linker import CellLinker
    from backend.main import AuditResponse, FindingContractItem

    preset_pdf = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "presets", "preset_1_ml_polarity.pdf",
    )
    assert os.path.exists(preset_pdf)

    doc_graph = FastPdfReader.process_pdf(preset_pdf)
    bundle = CellLinker().audit_document(doc_graph)

    # Validate full AuditResponse & FindingContractItem schemas (same contract as /api/v1/audit)
    validated_resp = AuditResponse.model_validate({
        "status": "success",
        "engine_version": "v3.5-grounded",
        "elapsed_seconds": 0.1,
        "readiness_score": 91.5,
        "skipped_count": 0,
        "pattern_summary": {"total_anomalies": len(bundle.get("findings", []))},
        "document_sha256": "deadbeef",
        "data": bundle,
    })
    payload = validated_resp.model_dump()
    assert payload["status"] == "success"
    bundle = payload["data"]
    assert bundle.get("render_scale") == 1.5
    assert "page_dimensions" in bundle and len(bundle["page_dimensions"]) >= 1

    findings = bundle.get("findings", [])
    assert len(findings) >= 1
    f0 = FindingContractItem.model_validate(findings[0]).model_dump()

    # New precision fields
    for key in (
        "page_width_pt",
        "page_height_pt",
        "render_scale",
        "claim_rects",
        "cell_page",
        "cell_page_width_pt",
        "cell_page_height_pt",
        "cell_rect",
    ):
        assert key in f0, f"Missing required finding field: {key}"

    assert f0["page_width_pt"] > 0 and f0["page_height_pt"] > 0
    assert f0["render_scale"] == 1.5
    assert isinstance(f0["claim_rects"], list) and len(f0["claim_rects"]) >= 1
    assert "value_rect" in f0["claim_source"]

    # Legacy backward-compatible fields still populated
    assert "bbox" in f0["claim_source"]
    assert "boxes" in f0["claim_source"]
    assert "table_bbox_norm" in f0
    for cell in f0["table_evidence"].get("cells", []):
        assert "bbox" in cell
        assert "bbox_approx" in cell




