"""
LOCUS Fast PDF Reader & X-Ray Page Renderer.
Layer 1 Perception - Powered by pypdfium2 (Apache-2.0 / BSD-3-Clause) & pdfplumber (MIT).
Zero-AGPL compliant.
"""

import os
import io
import re
import math
from typing import Dict, Any, List, Optional, Tuple
import pypdfium2 as pdfium
import pdfplumber
from PIL import Image
from backend.layer1_perception.table_geometry import TableGeometryExtractor

# Single source of truth for pypdfium2 page rendering scale (72-DPI PDF pt -> PNG px).
# Shared by renderer, OCR pixel-to-point conversion, and exposed to frontend as `render_scale`.
RENDER_SCALE: float = 1.5


def get_visible_page_frame(page) -> Tuple[float, float, float, float]:
    """
    Computes (crop_x0, crop_y0, vis_w, vis_h) in pdfplumber's rotated top-down coordinate space
    so pdfplumber coordinates map 1:1 onto the visible CropBox rendered by pypdfium2.

    SINGLE POINT OF COMPENSATION:
    Backend subtracts (crop_x0, crop_y0) ONCE here in FastPdfReader.process_pdf.
    All downstream tables, cells, claims, and frontend SVG overlays operate directly
    in normalized [0..vis_w] x [0..vis_h] 72-DPI PDF points and MUST NOT subtract
    cropbox offsets a second time.
    """
    page_obj = getattr(page, "page_obj", None)
    raw_mb = getattr(page_obj, "mediabox", None) if page_obj is not None else None
    raw_cb = getattr(page_obj, "cropbox", None) if page_obj is not None else None

    if raw_mb is None:
        raw_mb = getattr(page, "mediabox", None)
    if raw_cb is None:
        raw_cb = getattr(page, "cropbox", None) or raw_mb

    p_bbox = getattr(page, "bbox", (0.0, 0.0, float(page.width), float(page.height)))
    bx0 = float(p_bbox[0]) if len(p_bbox) >= 4 else 0.0
    by0 = float(p_bbox[1]) if len(p_bbox) >= 4 else 0.0

    if raw_mb is not None and raw_cb is not None and len(raw_mb) >= 4 and len(raw_cb) >= 4:
        mx0, my0, mx1, my1 = [float(v) for v in raw_mb[:4]]
        cx0, cy0, cx1, cy1 = [float(v) for v in raw_cb[:4]]
        cx0, cy0 = max(mx0, cx0), max(my0, cy0)
        cx1, cy1 = min(mx1, cx1), min(my1, cy1)
        m_left = cx0 - mx0
        m_right = mx1 - cx1
        m_bottom = cy0 - my0
        m_top = my1 - cy1
        cw = max(1.0, cx1 - cx0)
        ch = max(1.0, cy1 - cy0)
        rot = int(getattr(page, "rotation", 0) or 0) % 360
        if rot == 90:
            return bx0 + m_bottom, by0 + m_left, ch, cw
        elif rot == 180:
            return bx0 + m_right, by0 + m_bottom, cw, ch
        elif rot == 270:
            return bx0 + m_top, by0 + m_right, ch, cw
        else:
            return bx0 + m_left, by0 + m_top, cw, ch

    return bx0, by0, max(1.0, float(page.width)), max(1.0, float(page.height))


def _normalize_rect_to_visible(
    rect: Optional[List[float]],
    crop_x0: float,
    crop_y0: float,
    vis_w: float,
    vis_h: float,
) -> Optional[List[float]]:
    """Subtracts CropBox origin once and clamps to [0..vis_w] x [0..vis_h]. Returns None if degenerate."""
    if not rect or len(rect) < 4:
        return None
    try:
        x0, y0, x1, y1 = float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
        return None
    nx0 = max(0.0, min(vis_w, x0 - crop_x0))
    ny0 = max(0.0, min(vis_h, y0 - crop_y0))
    nx1 = max(0.0, min(vis_w, x1 - crop_x0))
    ny1 = max(0.0, min(vis_h, y1 - crop_y0))
    if nx1 <= nx0 or ny1 <= ny0:
        return None
    return [round(nx0, 1), round(ny0, 1), round(nx1, 1), round(ny1, 1)]


def _normalize_table_to_visible_frame(
    tbl: Dict[str, Any],
    crop_x0: float,
    crop_y0: float,
    vis_w: float,
    vis_h: float,
) -> Dict[str, Any]:
    """Normalizes table bbox and all cell rects into visible 72-DPI point space (single point of compensation)."""
    norm_tbbox = _normalize_rect_to_visible(tbl.get("bbox"), crop_x0, crop_y0, vis_w, vis_h)
    if norm_tbbox is not None:
        tbl["bbox"] = norm_tbbox
        tbl["y_bottom"] = norm_tbbox[3]
    tbl["page_width_pt"] = round(vis_w, 2)
    tbl["page_height_pt"] = round(vis_h, 2)

    for row in tbl.get("rows", []):
        if not isinstance(row, list):
            continue
        for cell in row:
            if not isinstance(cell, dict):
                continue
            raw_b = cell.get("cell_rect") or cell.get("bbox")
            norm_b = _normalize_rect_to_visible(raw_b, crop_x0, crop_y0, vis_w, vis_h)
            cell["bbox"] = norm_b
            cell["cell_rect"] = norm_b
            if "bbox_approx" not in cell:
                cell["bbox_approx"] = norm_b is None
    return tbl


def _group_words_into_visual_lines(words: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    C7 / 2.5: Groups words into visual lines using vertical midpoint `mid = (top + bottom) / 2`
    against the running mean `mid` of the current line with tolerance `0.5 * word_height`,
    then sorts words inside each line left-to-right by `x0`.
    Handles superscripts and mixed font sizes without splitting or reordering lines.
    """
    if not words:
        return []
    ordered = sorted(
        words,
        key=lambda item: (0.5 * (float(item["top"]) + float(item["bottom"])), float(item["x0"]))
    )
    lines: List[List[Dict[str, Any]]] = []
    line_mid_sums: List[float] = []
    line_h_sums: List[float] = []

    for w in ordered:
        w_top = float(w["top"])
        w_bot = float(w["bottom"])
        w_mid = 0.5 * (w_top + w_bot)
        w_h = max(4.0, w_bot - w_top)

        if not lines:
            lines.append([w])
            line_mid_sums.append(w_mid)
            line_h_sums.append(w_h)
            continue

        curr_cnt = len(lines[-1])
        mean_mid = line_mid_sums[-1] / curr_cnt
        mean_h = line_h_sums[-1] / curr_cnt
        tol = 0.5 * max(w_h, mean_h)

        if abs(w_mid - mean_mid) <= tol:
            lines[-1].append(w)
            line_mid_sums[-1] += w_mid
            line_h_sums[-1] += w_h
        else:
            lines.append([w])
            line_mid_sums.append(w_mid)
            line_h_sums.append(w_h)

    for line in lines:
        line.sort(key=lambda item: float(item["x0"]))
    return lines


class FastPdfReader:
    RENDER_SCALE: float = RENDER_SCALE

    @staticmethod
    def _px_to_pt(
        bbox: Optional[List[float]],
        crop_origin_px: Tuple[float, float] = (0.0, 0.0),
        scale: float = RENDER_SCALE,
    ) -> Optional[List[float]]:
        """
        Converts an OCR pixel bbox [x0, y0, x1, y1] (relative to cropped image)
        into normalized 72-DPI PDF points in the visible page frame:
            (px + crop_origin_px) / scale
        Returns None if bbox is missing, non-finite, or has width <= 0 or height <= 0.
        """
        if not bbox or len(bbox) < 4 or scale <= 0:
            return None
        try:
            px0, py0, px1, py1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            ox, oy = float(crop_origin_px[0]), float(crop_origin_px[1])
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(v) for v in (px0, py0, px1, py1, ox, oy)):
            return None
        if px1 <= px0 or py1 <= py0:
            return None
        return [
            round((px0 + ox) / scale, 1),
            round((py0 + oy) / scale, 1),
            round((px1 + ox) / scale, 1),
            round((py1 + oy) / scale, 1),
        ]

    @staticmethod
    def render_page_to_bytes(pdf_path: str, page_num: int, scale: float = RENDER_SCALE) -> bytes:
        """
        Renders a specific PDF page to PNG image bytes using pypdfium2.
        Page numbers are 1-based.
        """
        doc = pdfium.PdfDocument(pdf_path)
        page = doc[page_num - 1]
        image = page.render(scale=scale).to_pil()
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        doc.close()
        return buf.getvalue()

    @classmethod
    def process_pdf(
        cls,
        pdf_path: str,
        output_images_dir: Optional[str] = None,
        progress_callback: Optional[Any] = None,
        cancel_event: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Extracts DocumentGraph from PDF:
        - Pages rendered to PNG
        - Tables with cell bounding boxes
        - Extracted claims from narrative text (excluding table contents)
        - N_total detected from Bab 3
        """
        doc_pdfium = pdfium.PdfDocument(pdf_path)
        all_tables: List[Dict[str, Any]] = []
        all_claims: List[Dict[str, Any]] = []
        detected_total_n = None
        page_images_map: Dict[int, str] = {}
        page_dimensions: Dict[int, List[float]] = {}
        page_sizes: Dict[int, Dict[str, float]] = {}

        try:
            num_pages = len(doc_pdfium)

            # Render pages and save if output_images_dir is given (Fase 1: 5..25%)
            if output_images_dir:
                os.makedirs(output_images_dir, exist_ok=True)
                for p_idx in range(1, num_pages + 1):
                    if cancel_event and cancel_event.is_set():
                        return {
                            "cancelled": True,
                            "claims": [],
                            "tables": [],
                            "page_images": page_images_map,
                            "num_pages": num_pages,
                            "page_dimensions": page_dimensions,
                            "page_sizes": page_sizes,
                            "render_scale": RENDER_SCALE
                        }

                    if progress_callback:
                        pct = int(5 + (p_idx / max(1, num_pages)) * 20)
                        try:
                            progress_callback(
                                current_page=p_idx,
                                total_pages=num_pages,
                                step_name="Deteksi tabel",
                                pct=pct,
                                detail_text=f"Merender halaman {p_idx}/{num_pages}",
                                step_index=1
                            )
                        except TypeError:
                            progress_callback(p_idx, num_pages, f"Merender halaman {p_idx}/{num_pages}", pct)

                    page_p = doc_pdfium[p_idx - 1]
                    image = page_p.render(scale=RENDER_SCALE).to_pil()
                    img_filename = f"page_{p_idx}.png"
                    img_path = os.path.join(output_images_dir, img_filename)
                    image.save(img_path, format="PNG", compress_level=1)
                    page_images_map[p_idx] = f"/static/pages/{os.path.basename(output_images_dir)}/{img_filename}"
        finally:
            doc_pdfium.close()

        # Extract text & tables via pdfplumber (Fase 2: 25..50%)
        with pdfplumber.open(pdf_path) as pdf:
            current_chapter = "UNKNOWN"
            current_section_heading: Optional[str] = None
            current_section_variable: Optional[str] = None
            last_page_table_id: Optional[str] = None
            last_table_page: Optional[int] = None

            for page_idx, page in enumerate(pdf.pages, start=1):
                if cancel_event and cancel_event.is_set():
                    return {
                        "cancelled": True,
                        "claims": [],
                        "tables": all_tables,
                        "page_images": page_images_map,
                        "num_pages": num_pages,
                        "page_dimensions": page_dimensions,
                        "page_sizes": page_sizes,
                        "render_scale": RENDER_SCALE
                    }

                # Unified visible CropBox frame (72-DPI PDF points, /Rotate-aware).
                # Single point of CropBox compensation: origin offsets stored as 0.0 because
                # all emitted table/cell/claim coordinates are pre-compensated below.
                crop_x0, crop_y0, vis_w, vis_h = get_visible_page_frame(page)
                page_dimensions[page_idx] = [
                    round(vis_w, 2),
                    round(vis_h, 2),
                    0.0,
                    0.0
                ]
                page_sizes[page_idx] = {
                    "page_width_pt": round(vis_w, 2),
                    "page_height_pt": round(vis_h, 2)
                }
                page_text = page.extract_text() or ""
                raw_words = page.extract_words() or []

                if progress_callback:
                    pct = int(25 + (page_idx / max(1, num_pages)) * 25)
                    try:
                        progress_callback(
                            current_page=page_idx,
                            total_pages=num_pages,
                            step_name="Pemisahan klaim",
                            pct=pct,
                            detail_text=f"Mengekstrak tabel & narasi halaman {page_idx}/{num_pages}",
                            step_index=2
                        )
                    except TypeError:
                        progress_callback(page_idx, num_pages, f"Mengekstrak tabel & narasi halaman {page_idx}/{num_pages}", pct)

                # Chapter detection
                if "BAB III" in page_text.upper() or "METODE" in page_text.upper():
                    current_chapter = "BAB_3"
                elif "BAB IV" in page_text.upper() or "HASIL" in page_text.upper():
                    current_chapter = "BAB_4"
                elif "BAB V" in page_text.upper() or "KESIMPULAN" in page_text.upper():
                    current_chapter = "BAB_5"

                # Detect N_total in Bab 3
                if current_chapter == "BAB_3" and detected_total_n is None:
                    n_match = re.search(r"\b(?:sampel|jumlah|responden|subjek|N)\s*(?:sebesar|=|\badalah)?\s*(\d{2,4})\b", page_text, re.IGNORECASE)
                    if n_match:
                        try:
                            detected_total_n = int(n_match.group(1))
                        except Exception:
                            pass

                # Extract tables on this page reusing pre-extracted words, then normalize ONCE to visible CropBox space
                page_tables = TableGeometryExtractor.extract_tables_from_pdfplumber_page(page, page_idx, pre_extracted_words=raw_words)
                page_tables = [
                    _normalize_table_to_visible_frame(t, crop_x0, crop_y0, vis_w, vis_h)
                    for t in page_tables
                ]

                # OCR Fallback for scanned/image tables if vector tables are empty
                if not page_tables and hasattr(page, "images") and page.images and output_images_dir:
                    for img_meta in page.images:
                        w_img = float(img_meta.get("width", 0))
                        h_img = float(img_meta.get("height", 0))
                        if w_img >= 180 and h_img >= 80:
                            try:
                                import numpy as np
                                from backend.layer1_perception.ocr_fallback import OcrTableFallback
                                page_img_path = os.path.join(output_images_dir, f"page_{page_idx}.png")
                                if os.path.exists(page_img_path):
                                    with Image.open(page_img_path) as full_img:
                                        img_region_rect = _normalize_rect_to_visible(
                                            [
                                                float(img_meta.get("x0", crop_x0)),
                                                float(img_meta.get("top", crop_y0)),
                                                float(img_meta.get("x1", crop_x0 + vis_w)),
                                                float(img_meta.get("bottom", crop_y0 + vis_h)),
                                            ],
                                            crop_x0, crop_y0, vis_w, vis_h
                                        )
                                        if not img_region_rect:
                                            continue

                                        scale_x = full_img.width / vis_w if vis_w > 0 else RENDER_SCALE
                                        scale_y = full_img.height / vis_h if vis_h > 0 else RENDER_SCALE
                                        eff_scale = 0.5 * (scale_x + scale_y) if (scale_x > 0 and scale_y > 0) else RENDER_SCALE

                                        crop_px_x0 = max(0, int(round(img_region_rect[0] * scale_x)))
                                        crop_px_y0 = max(0, int(round(img_region_rect[1] * scale_y)))
                                        crop_px_x1 = min(full_img.width, int(round(img_region_rect[2] * scale_x)))
                                        crop_px_y1 = min(full_img.height, int(round(img_region_rect[3] * scale_y)))

                                        if crop_px_x1 > crop_px_x0 and crop_px_y1 > crop_px_y0:
                                            cropped = full_img.crop((crop_px_x0, crop_px_y0, crop_px_x1, crop_px_y1))
                                            ocr_res = OcrTableFallback.extract_table_from_image(np.array(cropped))
                                            if ocr_res and ocr_res.get("rows"):
                                                ocr_rows = []
                                                for r_idx, row_cells in enumerate(ocr_res["rows"]):
                                                    s_row = []
                                                    for c_idx, cell in enumerate(row_cells):
                                                        c_text = ""
                                                        raw_px_bbox = None
                                                        if isinstance(cell, str):
                                                            c_text = cell
                                                        elif isinstance(cell, dict):
                                                            c_text = cell.get("text") or cell.get("raw_val") or ""
                                                            raw_px_bbox = cell.get("bbox")
                                                        else:
                                                            c_text = str(cell)

                                                        pt_bbox = cls._px_to_pt(
                                                            raw_px_bbox,
                                                            crop_origin_px=(crop_px_x0, crop_px_y0),
                                                            scale=eff_scale,
                                                        )
                                                        if pt_bbox is not None:
                                                            # Clamp converted OCR cell rect to the image region
                                                            pt_bbox = [
                                                                round(max(img_region_rect[0], min(img_region_rect[2], pt_bbox[0])), 1),
                                                                round(max(img_region_rect[1], min(img_region_rect[3], pt_bbox[1])), 1),
                                                                round(max(img_region_rect[0], min(img_region_rect[2], pt_bbox[2])), 1),
                                                                round(max(img_region_rect[1], min(img_region_rect[3], pt_bbox[3])), 1),
                                                            ]
                                                            if pt_bbox[2] <= pt_bbox[0] or pt_bbox[3] <= pt_bbox[1]:
                                                                pt_bbox = None

                                                        if pt_bbox is None:
                                                            cell_rect = list(img_region_rect)
                                                            is_approx = True
                                                        else:
                                                            cell_rect = pt_bbox
                                                            is_approx = False

                                                        num_val = None
                                                        try:
                                                            c_clean = re.sub(r"^([+-]?)\s*[,.](\d+)$", r"\g<1>0.\g<2>", c_text.strip())
                                                            num_val = float(c_clean.replace(",", "."))
                                                        except Exception:
                                                            pass

                                                        s_row.append({
                                                            "row": r_idx + 1,
                                                            "col": c_idx + 1,
                                                            "row_idx": r_idx,
                                                            "col_idx": c_idx,
                                                            "text": c_text,
                                                            "raw_val": c_text,
                                                            "num_val": num_val,
                                                            "header_path": f"Kolom_{c_idx+1}",
                                                            "row_label": f"Baris_{r_idx+1}",
                                                            "bbox": cell_rect,
                                                            "cell_rect": cell_rect,
                                                            "bbox_approx": is_approx
                                                        })
                                                    if s_row:
                                                        ocr_rows.append(s_row)

                                                if ocr_rows:
                                                    ocr_tbl_dict = {
                                                        "table_id": f"Tabel_OCR_{page_idx}_1",
                                                        "page": page_idx,
                                                        "table_num": "OCR",
                                                        "normalized_id": f"OCR_{page_idx}",
                                                        "page_width_pt": round(vis_w, 2),
                                                        "page_height_pt": round(vis_h, 2),
                                                        "y_bottom": img_region_rect[3],
                                                        "caption": f"Tabel Gambar Halaman {page_idx}",
                                                        "bbox": list(img_region_rect),
                                                        "num_rows": len(ocr_rows),
                                                        "num_cols": max(len(r) for r in ocr_rows),
                                                        "header_paths": [f"Kolom_{i+1}" for i in range(max(len(r) for r in ocr_rows))],
                                                        "rows": ocr_rows
                                                    }
                                                    page_tables.append(ocr_tbl_dict)
                                                    break
                            except Exception:
                                pass

                # Urutkan page_tables berdasarkan bbox[1] (atas ke bawah)
                page_tables.sort(
                    key=lambda t: float(t.get("bbox", [0, 0, 0, 0])[1]) if len(t.get("bbox", [])) >= 4 else 0.0
                )
                all_tables.extend(page_tables)
                if page_tables:
                    current_section_variable = None

                # Normalize narrative words ONCE into the visible CropBox coordinate frame [0..vis_w] x [0..vis_h]
                words = []
                for w in raw_words:
                    nw = dict(w)
                    nw["x0"] = float(w["x0"]) - crop_x0
                    nw["x1"] = float(w["x1"]) - crop_x0
                    nw["top"] = float(w["top"]) - crop_y0
                    nw["bottom"] = float(w["bottom"]) - crop_y0
                    if nw["x1"] > 0.0 and nw["x0"] < vis_w and nw["bottom"] > 0.0 and nw["top"] < vis_h:
                        words.append(nw)

                # Determine table bounding boxes to subtract table words from narrative text
                t_bboxes = [t["bbox"] for t in page_tables if "bbox" in t and t["bbox"] and len(t["bbox"]) == 4]
                page_h = vis_h

                # Filter words that are strictly OUTSIDE all table bounding boxes (with 6pt padding)
                # Header/footer check operates on normalized visible coordinates (C8 CropBox-aware).
                clean_words = []
                for w in words:
                    wx = 0.5 * (float(w["x0"]) + float(w["x1"]))
                    wy = 0.5 * (float(w["top"]) + float(w["bottom"]))
                    in_any_table = any(
                        (bx[0] - 6.0) <= wx <= (bx[2] + 6.0) and (bx[1] - 6.0) <= wy <= (bx[3] + 6.0)
                        for bx in t_bboxes
                    )
                    # Skip header/footer and lone page numbers at top
                    is_header_footer = (wy < 40.0) or (wy > (page_h - 40.0)) or (wy < 65.0 and re.match(r"^\d+$", w["text"].strip()))
                    if not in_any_table and not is_header_footer:
                        clean_words.append(w)

                # Group narrative words into visual lines using midpoint mean clustering (C7)
                lines: List[List[Dict[str, Any]]] = _group_words_into_visual_lines(clean_words)

                # Assemble into tight sentence-level claims and formula clauses
                curr_tokens: List[Dict[str, Any]] = []

                def _flush_claim(tokens: List[Dict[str, Any]], is_formula: bool = False):
                    if not tokens:
                        return
                    sent = " ".join(t["text"] for t in tokens).strip()
                    min_len = 6 if is_formula else 15
                    if len(sent) >= min_len:
                        tok_lines = _group_words_into_visual_lines(tokens)

                        line_boxes = []
                        tok_boxes = []
                        for tl in tok_lines:
                            lx0 = min(float(t["x0"]) for t in tl)
                            ltop = min(float(t["top"]) for t in tl)
                            lx1 = max(float(t["x1"]) for t in tl)
                            lbottom = max(float(t["bottom"]) for t in tl)
                            if lx1 > lx0 and lbottom > ltop:
                                line_boxes.append([round(lx0, 1), round(ltop, 1), round(lx1, 1), round(lbottom, 1)])
                            for t in tl:
                                tx0 = round(float(t["x0"]), 1)
                                ttop = round(float(t["top"]), 1)
                                tx1 = round(float(t["x1"]), 1)
                                tbot = round(float(t["bottom"]), 1)
                                if tx1 > tx0 and tbot > ttop:
                                    tok_boxes.append([str(t["text"]), tx0, ttop, tx1, tbot])

                        if not line_boxes:
                            return

                        x0 = min(b[0] for b in line_boxes)
                        top = min(b[1] for b in line_boxes)
                        x1 = max(b[2] for b in line_boxes)
                        bottom = max(b[3] for b in line_boxes)

                        # Tentukan claim_scope_table_id: pilih tabel terakhir di page_tables yang t["bbox"][1] <= top + 10
                        candidate_tables = [
                            t for t in page_tables
                            if len(t.get("bbox", [])) >= 4 and t["bbox"][1] <= (top + 10.0)
                        ]
                        if candidate_tables:
                            claim_scope_table_id = candidate_tables[-1].get("table_id")
                        elif last_page_table_id and last_table_page == (page_idx - 1) and top <= 250.0:
                            claim_scope_table_id = last_page_table_id
                        else:
                            claim_scope_table_id = None

                        all_claims.append({
                            "claim_id": f"C_{page_idx}_{len(all_claims)+1}",
                            "page": page_idx,
                            "page_width_pt": round(vis_w, 2),
                            "page_height_pt": round(vis_h, 2),
                            "text": sent,
                            "chapter": current_chapter,
                            "section_heading": current_section_heading,
                            "section_variable": current_section_variable,
                            "scope_table_id": claim_scope_table_id,
                            "bbox": [round(x0, 1), round(top, 1), round(x1, 1), round(bottom, 1)],
                            "claim_y_top": round(top, 1),
                            "boxes": line_boxes,
                            "claim_rects": line_boxes,
                            "tok_boxes": tok_boxes,
                            "is_formula": is_formula
                        })

                last_line_bottom: Optional[float] = None
                for line in lines:
                    line_text = " ".join(w["text"] for w in line).strip()
                    # Skip table captions or standalone headers
                    if re.match(r"^(Tabel\s+(?:[IVX]+|\d+)|Sumber\s*:|Hasil\s+Uji)", line_text, re.IGNORECASE):
                        continue

                    line_top = float(line[0]["top"])

                    # Jika ada tabel di antara last_line_bottom dan line_top, WAJIB flush curr_tokens terlebih dahulu
                    if curr_tokens and last_line_bottom is not None:
                        has_table_between = any(
                            ((last_line_bottom - 5.0) <= t["bbox"][1] <= (line_top + 5.0))
                            or ((last_line_bottom - 5.0) <= t["bbox"][3] <= (line_top + 5.0))
                            or (t["bbox"][1] <= last_line_bottom and t["bbox"][3] >= line_top)
                            for t in page_tables
                            if len(t.get("bbox", [])) >= 4
                        )
                        if has_table_between:
                            _flush_claim(curr_tokens, is_formula=False)
                            curr_tokens = []

                    # Reset last_page_table_id saat melewati heading BAB baru
                    if re.match(r"^BAB\s+([IVX]+|\d+)\b", line_text, re.IGNORECASE):
                        last_page_table_id = None
                        last_table_page = None

                    # Only flush across lines if there is a GENUINE paragraph gap (> 20pt, exceeding 1.5 line spacing)
                    # or an explicit new heading/section number
                    m_sec_hd = re.match(r"^(\d+\.\d+(?:\.\d+)*)\s+([A-Za-z\s]{2,40})$", line_text)
                    if m_sec_hd:
                        current_section_heading = line_text
                        current_section_variable = m_sec_hd.group(2).strip()

                    is_new_section_or_item = bool(
                        re.match(r"^(\d+(\.\d+)*\s+[A-Z]|Bab\s+[IVX]+|[A-Z][a-z0-9\s\-]+:|\d+\.\s+[A-Z]|[a-z]\.\s+[A-Z])", line_text)
                    )
                    if curr_tokens and (
                        (last_line_bottom is not None and (line_top - last_line_bottom) > 20.0)
                        or is_new_section_or_item
                    ):
                        _flush_claim(curr_tokens, is_formula=False)
                        curr_tokens = []

                    last_line_bottom = max(float(w["bottom"]) for w in line)

                    # Check for inline mathematical formula clauses
                    is_formula_line = bool(
                        re.search(r"=\s*([+-]?\d+[,.]\d+|[A-Za-z]+|\/|√)", line_text)
                        and ("Z" in line_text or "√" in line_text or "/" in line_text or "Skewness" in line_text or "Kurtosis" in line_text)
                    )

                    for w_idx, w in enumerate(line):
                        curr_tokens.append(w)
                        tok = w["text"].strip()
                        # Strict end-of-sentence punctuation: only end if followed by word break or abbreviation check
                        is_abbreviation = bool(
                            re.match(r"^(No\.|Hal\.|Dr\.|Prof\.|Cs\.|dkk\.|dll\.|dst\.|vol\.|ed\.|e\.g\.|i\.e\.|Sig\.|vs\.|ca\.|dept\.|univ\.|tabel\.|gb\.|gbr\.|lamp\.|\d+\.)$", tok, re.IGNORECASE)
                        )
                        next_is_lower = False
                        if w_idx + 1 < len(line):
                            next_tok = line[w_idx + 1]["text"].strip()
                            if next_tok and next_tok[0].islower():
                                next_is_lower = True

                        is_end_punct = (
                            tok.endswith((".", "!", "?"))
                            and not is_abbreviation
                            and not next_is_lower
                        )
                        if is_end_punct:
                            _flush_claim(curr_tokens, is_formula=False)
                            curr_tokens = []
                        elif len(curr_tokens) >= 50 and tok.endswith((",", ";", ":")):
                            # Natural clause break for unusually long compound sentences
                            _flush_claim(curr_tokens, is_formula=False)
                            curr_tokens = []

                    if is_formula_line and curr_tokens:
                        _flush_claim(curr_tokens, is_formula=True)
                        curr_tokens = []
                    elif re.search(r":\s*$", line_text) and curr_tokens:
                        # Colon ending introductory sentence (e.g. "...sebagai berikut :")
                        _flush_claim(curr_tokens, is_formula=False)
                        curr_tokens = []

                if curr_tokens:
                    _flush_claim(curr_tokens, is_formula=False)
                    curr_tokens = []

                if page_tables:
                    last_page_table_id = page_tables[-1].get("table_id")
                    last_table_page = page_idx

        # Stitch cross-page tables
        stitched_tables = TableGeometryExtractor.stitch_cross_page_tables(all_tables)

        return {
            "num_pages": num_pages,
            "detected_total_n": detected_total_n,
            "tables": stitched_tables,
            "claims": all_claims,
            "page_images": page_images_map,
            "page_dimensions": page_dimensions,
            "page_sizes": page_sizes,
            "render_scale": RENDER_SCALE
        }
