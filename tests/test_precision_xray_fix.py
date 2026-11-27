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
