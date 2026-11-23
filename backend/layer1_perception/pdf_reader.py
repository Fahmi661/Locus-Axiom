"""
LOCUS Fast PDF Reader & X-Ray Page Renderer.
Layer 1 Perception - Powered by pypdfium2 (Apache-2.0 / BSD-3-Clause) & pdfplumber (MIT).
Zero-AGPL compliant.
"""

import os
import io
import re
from typing import Dict, Any, List, Optional
import pypdfium2 as pdfium
import pdfplumber
from PIL import Image
from backend.layer1_perception.table_geometry import TableGeometryExtractor


class FastPdfReader:
    @staticmethod
    def render_page_to_bytes(pdf_path: str, page_num: int, scale: float = 1.5) -> bytes:
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
                            "page_dimensions": page_dimensions
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
                    image = page_p.render(scale=1.5).to_pil()
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

            for page_idx, page in enumerate(pdf.pages, start=1):
                if cancel_event and cancel_event.is_set():
                    return {
                        "cancelled": True,
                        "claims": [],
                        "tables": all_tables,
                        "page_images": page_images_map,
                        "num_pages": num_pages,
                        "page_dimensions": page_dimensions
                    }

                p_box = getattr(page, "bbox", [0, 0, page.width, page.height])
                page_dimensions[page_idx] = [
                    round(float(page.width), 2),
                    round(float(page.height), 2),
                    round(float(p_box[0]), 2) if len(p_box) >= 4 else 0.0,
                    round(float(p_box[1]), 2) if len(p_box) >= 4 else 0.0
                ]
                page_text = page.extract_text() or ""
                words = page.extract_words() or []

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

                # Extract tables on this page reusing pre-extracted words
                page_tables = TableGeometryExtractor.extract_tables_from_pdfplumber_page(page, page_idx, pre_extracted_words=words)

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
                                        pw = float(page.width) or 1.0
                                        ph = float(page.height) or 1.0
                                        scale_x = full_img.width / pw
                                        scale_y = full_img.height / ph

                                        x0 = max(0, int(float(img_meta.get("x0", 0)) * scale_x))
                                        y0 = max(0, int(float(img_meta.get("top", 0)) * scale_y))
                                        x1 = min(full_img.width, int(float(img_meta.get("x1", pw)) * scale_x))
                                        y1 = min(full_img.height, int(float(img_meta.get("bottom", ph)) * scale_y))

                                        if x1 > x0 and y1 > y0:
                                            cropped = full_img.crop((x0, y0, x1, y1))
                                            ocr_res = OcrTableFallback.extract_table_from_image(np.array(cropped))
                                            if ocr_res and ocr_res.get("rows"):
                                                ocr_rows = []
                                                for r_idx, row_cells in enumerate(ocr_res["rows"]):
                                                    s_row = []
                                                    for c_idx, cell in enumerate(row_cells):
                                                        c_text = ""
                                                        c_bbox = [0, 0, 0, 0]
                                                        if isinstance(cell, str):
                                                            c_text = cell
                                                        elif isinstance(cell, dict):
                                                            c_text = cell.get("text") or cell.get("raw_val") or ""
                                                            c_bbox = cell.get("bbox", [0, 0, 0, 0])
                                                        else:
                                                            c_text = str(cell)

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
                                                            "bbox": c_bbox
                                                        })
                                                    if s_row:
                                                        ocr_rows.append(s_row)

                                                if ocr_rows:
                                                    ocr_tbl_dict = {
                                                        "table_id": f"Tabel_OCR_{page_idx}_1",
                                                        "page": page_idx,
                                                        "table_num": "OCR",
                                                        "normalized_id": f"OCR_{page_idx}",
                                                        "y_bottom": round(float(img_meta.get("bottom", 0)), 1),
                                                        "caption": f"Tabel Gambar Halaman {page_idx}",
                                                        "bbox": [
                                                            round(float(img_meta.get("x0", 0)), 1),
                                                            round(float(img_meta.get("top", 0)), 1),
                                                            round(float(img_meta.get("x1", 0)), 1),
                                                            round(float(img_meta.get("bottom", 0)), 1)
                                                        ],
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

                # Determine table bounding boxes to subtract table words from narrative text
                t_bboxes = [t["bbox"] for t in page_tables if "bbox" in t and len(t["bbox"]) == 4]
                page_h = float(page.height)

                # Filter words that are strictly OUTSIDE all table bounding boxes (with 6pt padding)
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

                # Group narrative words into visual lines based on vertical overlap
                clean_words.sort(key=lambda item: (float(item["top"]), float(item["x0"])))
                lines: List[List[Dict[str, Any]]] = []
                for w in clean_words:
                    if not lines or abs(float(w["top"]) - float(lines[-1][0]["top"])) > 5.5:
                        lines.append([w])
                    else:
                        lines[-1].append(w)
                for line in lines:
                    line.sort(key=lambda item: float(item["x0"]))

                # Assemble into tight sentence-level claims and formula clauses
                curr_tokens: List[Dict[str, Any]] = []

                def _flush_claim(tokens: List[Dict[str, Any]], is_formula: bool = False):
                    if not tokens:
                        return
                    sent = " ".join(t["text"] for t in tokens).strip()
                    min_len = 6 if is_formula else 15
                    if len(sent) >= min_len:
                        sorted_toks = sorted(tokens, key=lambda t: (float(t["top"]), float(t["x0"])))
                        tok_lines: List[List[Dict[str, Any]]] = []
                        for t in sorted_toks:
                            if not tok_lines or abs(float(t["top"]) - float(tok_lines[-1][0]["top"])) > 5.0:
                                tok_lines.append([t])
                            else:
                                tok_lines[-1].append(t)

                        line_boxes = []
                        for tl in tok_lines:
                            lx0 = min(float(t["x0"]) for t in tl)
                            ltop = min(float(t["top"]) for t in tl)
                            lx1 = max(float(t["x1"]) for t in tl)
                            lbottom = max(float(t["bottom"]) for t in tl)
                            line_boxes.append([round(lx0, 1), round(ltop, 1), round(lx1, 1), round(lbottom, 1)])

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
                        else:
                            claim_scope_table_id = last_page_table_id

                        all_claims.append({
                            "claim_id": f"C_{page_idx}_{len(all_claims)+1}",
                            "page": page_idx,
                            "text": sent,
                            "chapter": current_chapter,
                            "section_heading": current_section_heading,
                            "section_variable": current_section_variable,
                            "scope_table_id": claim_scope_table_id,
                            "bbox": [round(x0, 1), round(top, 1), round(x1, 1), round(bottom, 1)],
                            "claim_y_top": round(top, 1),
                            "boxes": line_boxes,
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

        # Stitch cross-page tables
        stitched_tables = TableGeometryExtractor.stitch_cross_page_tables(all_tables)

        return {
            "num_pages": num_pages,
            "detected_total_n": detected_total_n,
            "tables": stitched_tables,
            "claims": all_claims,
            "page_images": page_images_map,
            "page_dimensions": page_dimensions
        }
