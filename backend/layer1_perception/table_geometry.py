"""
LOCUS Table Geometry & HeaderPath Tree Builder.
Layer 1 Perception - Extracts 3-line scientific tables (tabel tiga garis),
cell bounding boxes, and hierarchical HeaderPaths via X-coordinate density clustering.
"""

from typing import List, Dict, Any, Optional, Tuple
import re
import pdfplumber
from backend.layer1_perception.number_normalizer import NumberNormalizer


HEADER_KEYWORDS = {
    "n", "minimum", "maximum", "mean", "std", "frequency", "percent",
    "sig", "t", "f", "valid", "frekuensi", "persentase", "jumlah",
    "total", "df", "p-value", "keterangan", "variabel"
}


def has_sub_header(sub_row: List[Any], num_cols: Optional[int] = None) -> bool:
    """
    Checks if a row is a sub-header row.
    STRICT: Only True if valid numeric cells count is <= 1 (if cols >= 5) or 0
    AND contains at least one header keyword.
    Never eats the first data row (e.g. 'Ketepatan Waktu | 96 | ,00 | 1,00').
    """
    if not sub_row:
        return False
    if num_cols is None:
        num_cols = len(sub_row)
    num_numeric = sum(1 for v in sub_row if v and NumberNormalizer.parse_numeric(str(v)) is not None)
    max_allowed_num = 1 if num_cols >= 5 else 0
    if num_numeric <= max_allowed_num:
        has_kw = any(
            any(kw in str(v).lower() for kw in HEADER_KEYWORDS)
            for v in sub_row if v
        )
        if has_kw:
            return True
    return False


def classify_table_type(
    header_paths: Optional[List[str]] = None,
    rows: Any = None,
    caption: str = ""
) -> str:
    """
    Classifies table type into one of:
    - SPSS_LIKERT_FREQ
    - ASSUMPTION_TEST
    - REGRESSION_COEFF
    - CLASSIFICATION_ML
    - DESCRIPTIVE_STATS
    - GENERAL_TABLE
    """
    tokens = []
    cap_lower = (caption or "").lower()
    if cap_lower:
        tokens.append(cap_lower)

    if header_paths:
        for hp in header_paths:
            if hp:
                tokens.append(str(hp).lower())

    if rows:
        for r in rows:
            if isinstance(r, list):
                for cell in r:
                    if isinstance(cell, dict):
                        txt = cell.get("text") or cell.get("raw_val") or cell.get("row_label") or ""
                        if txt:
                            tokens.append(str(txt).lower())
                    elif cell:
                        tokens.append(str(cell).lower())
            elif isinstance(r, dict):
                for v in r.values():
                    if v:
                        tokens.append(str(v).lower())
            elif r:
                tokens.append(str(r).lower())

    all_text = " ".join(tokens)
    word_set = set(re.findall(r"[a-z0-9_.\-]+", all_text))

    # 1. SPSS_LIKERT_FREQ
    has_freq = any(w in all_text for w in ["frequency", "frekuensi", "tanggapan responden"])
    has_pct = any(w in all_text for w in ["percent", "persen", "kumulatif", "cumulative", "valid percent"])
    has_likert_levels = (
        ("sts" in word_set and "ss" in word_set) or
        ("sangat tidak setuju" in all_text and "sangat setuju" in all_text) or
        ("tidak setuju" in all_text and "setuju" in all_text and has_freq)
    )
    if (has_freq and has_pct) or has_likert_levels or "distribusi frekuensi" in cap_lower:
        return "SPSS_LIKERT_FREQ"

    # 2. ASSUMPTION_TEST
    has_normality = any(w in all_text for w in ["kolmogorov", "smirnov", "shapiro-wilk", "shapiro", "jarque", "bera", "asymp. sig", "asymp.sig"])
    has_autocorr = any(w in all_text for w in ["durbin-watson", "durbin watson"]) or ("durbin" in all_text and "watson" in all_text) or ("dw" in word_set and "autokorelasi" in all_text)
    has_multicol = ("vif" in word_set or "variance inflation" in all_text) and any(w in all_text for w in ["tolerance", "toleransi", "collinearity", "multikolinearitas"])
    has_hetero = any(w in all_text for w in ["glejser", "park", "white", "heteroskedastisitas", "heteroskedastis"])
    has_unit_root = any(w in all_text for w in ["augmented dickey", "dickey-fuller", "unit root"])
    has_assumption_cap = any(w in cap_lower for w in ["uji normalitas", "uji multikolinearitas", "uji autokorelasi", "uji heteroskedastisitas", "uji asumsi klasik", "asumsi klasik"])
    if has_normality or has_autocorr or has_multicol or has_hetero or has_unit_root or has_assumption_cap:
        return "ASSUMPTION_TEST"

    # 3. REGRESSION_COEFF
    has_reg_headers = (
        any(w in all_text for w in ["unstandardized", "coefficients", "koefisien regresi", "persamaan regresi"]) or
        (("std. error" in all_text or "std error" in all_text) and any(w in word_set for w in ["t", "beta", "b"]) and any(w in word_set for w in ["sig", "sig."])) or
        (("t hitung" in all_text or "t-hitung" in all_text or "t-statistic" in all_text or "t-stat" in all_text) and ("sig" in word_set or "p-value" in all_text or "prob" in all_text)) or
        (("f hitung" in all_text or "f-hitung" in all_text or "f-statistic" in all_text or "f-stat" in all_text) and ("sig" in word_set or "p-value" in all_text or "prob" in all_text)) or
        (("konstanta" in all_text or "constant" in all_text or "(constant)" in all_text) and ("b" in word_set or "beta" in word_set or "koefisien" in all_text))
    )
    has_reg_cap = any(w in cap_lower for w in ["hasil regresi", "koefisien regresi", "analisis regresi", "uji t", "uji f", "regresi linear", "regresi berganda", "regresi logistik", "regresi data panel"])
    if has_reg_headers or has_reg_cap:
        return "REGRESSION_COEFF"

    # 4. CLASSIFICATION_ML
    has_cls_metrics = (
        ("precision" in all_text and "recall" in all_text) or
        any(w in all_text for w in ["f1-score", "f1 score", "f1-measure", "confusion matrix", "matrix konfusi"]) or
        (("accuracy" in all_text or "akurasi" in all_text) and any(w in word_set for w in ["precision", "recall", "auc", "roc", "f1"])) or
        (any(m in word_set for m in ["rmse", "mae", "mape", "mse"]) and any(w in all_text for w in ["epoch", "loss", "baseline", "xgboost", "random forest", "arima", "hybrid", "model", "prediksi"]))
    )
    has_ml_cap = any(w in cap_lower for w in ["confusion matrix", "klasifikasi", "evaluasi model", "performa model", "hasil klasifikasi", "hasil pengujian model"])
    if has_cls_metrics or has_ml_cap:
        return "CLASSIFICATION_ML"

    # 5. DESCRIPTIVE_STATS
    has_desc_terms = (
        (any(w in word_set for w in ["mean", "rata-rata"]) and any(w in word_set for w in ["minimum", "min"]) and any(w in word_set for w in ["maximum", "max"])) or
        (any(w in all_text for w in ["std. deviation", "std deviation", "standar deviasi"]) and any(w in word_set for w in ["mean", "rata-rata", "n", "min", "max"])) or
        any(w in cap_lower for w in ["statistik deskriptif", "deskriptif", "descriptive statistics"])
    )
    if has_desc_terms:
        return "DESCRIPTIVE_STATS"

    # 6. Fallback
    return "GENERAL_TABLE"


class TableGeometryExtractor:
    @classmethod
    def classify_table_type(
        cls,
        header_paths: Optional[List[str]] = None,
        rows: Any = None,
        caption: str = ""
    ) -> str:
        return classify_table_type(header_paths, rows, caption)
    @staticmethod
    def _group_words_into_cells(words: List[Dict[str, Any]], max_word_gap: float = 25.0) -> List[Dict[str, Any]]:
        """
        Groups words on the same line into cells based on horizontal word spacing.
        """
        if not words:
            return []
        words.sort(key=lambda w: w["x0"])
        cells: List[Dict[str, Any]] = []
        curr = [words[0]]

        for w in words[1:]:
            if (w["x0"] - curr[-1]["x1"]) <= max_word_gap:
                curr.append(w)
            else:
                cell_text = " ".join(x["text"] for x in curr).strip()
                cells.append({
                    "text": cell_text,
                    "x0": curr[0]["x0"],
                    "x1": curr[-1]["x1"],
                    "top": min(x["top"] for x in curr),
                    "bottom": max(x["bottom"] for x in curr)
                })
                curr = [w]

        if curr:
            cell_text = " ".join(x["text"] for x in curr).strip()
            cells.append({
                "text": cell_text,
                "x0": curr[0]["x0"],
                "x1": curr[-1]["x1"],
                "top": min(x["top"] for x in curr),
                "bottom": max(x["bottom"] for x in curr)
            })

        return cells

    @staticmethod
    def _detect_table_caption(page_words: List[Dict[str, Any]], bbox: List[float]) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        """
        Detects table title/caption, table number, and canonical normalized_id in the 95pt window above bbox.
        """
        if not page_words or len(bbox) < 4:
            return None, None, None
        import re
        from backend.layer2_core.spss_likert_engine import normalize_table_id
        t_top = bbox[1]
        above_words = [
            w for w in page_words
            if (t_top - 95.0 <= float(w.get("bottom", 0)) <= t_top + 6.0) and
               (bbox[0] - 40.0 <= float(w.get("x0", 0)) <= bbox[2] + 40.0)
        ]
        if not above_words:
            return None, None, None
        above_words.sort(key=lambda w: (float(w["top"]), float(w["x0"])))
        above_text = " ".join(w["text"] for w in above_words)

        matches = list(re.finditer(r"\b(Tabel\s+([IVX]+|\d+)(?:\s*[.\-]\s*(\d+))?[\.\:\s]*([^\n\r]*))", above_text, re.IGNORECASE))
        if matches:
            last_m = matches[-1]
            full_caption = last_m.group(0).strip()
            norm_id = normalize_table_id(full_caption)
            tbl_num = None
            if last_m.group(3):
                try:
                    tbl_num = int(last_m.group(3))
                except Exception:
                    pass
            elif last_m.group(2) and last_m.group(2).isdigit():
                tbl_num = int(last_m.group(2))
            return full_caption, tbl_num, norm_id
        return None, None, None

    @classmethod
    def extract_3line_table(
        cls,
        page,
        page_num: int,
        pre_extracted_words: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts borderless 3-line scientific tables by detecting horizontal lines
        and grouping tokens per line into cells.
        """
        lines = page.lines or []
        h_lines = [
            l for l in lines
            if abs(l.get("top", 0) - l.get("bottom", 0)) <= 3 and abs(l.get("x1", 0) - l.get("x0", 0)) >= 150
        ]
        h_lines.sort(key=lambda l: l["top"])

        if len(h_lines) < 2:
            return None

        top_rule = h_lines[0]
        mid_rule = h_lines[1] if len(h_lines) >= 3 else None
        bottom_rule = h_lines[-1]

        y_top = top_rule["top"]
        y_bottom = bottom_rule["bottom"]
        x_min = min(l["x0"] for l in h_lines)
        x_max = max(l["x1"] for l in h_lines)

        all_words = pre_extracted_words if pre_extracted_words is not None else (page.extract_words() or [])
        table_words = [w for w in all_words if y_top - 2 <= w["top"] and w["bottom"] <= y_bottom + 4]
        if not table_words:
            return None

        # Group words into line rows by Y
        table_words.sort(key=lambda w: (w["top"], w["x0"]))
        lines_grouped: List[List[Dict[str, Any]]] = []
        curr_line: List[Dict[str, Any]] = []
        curr_y = None

        for w in table_words:
            if curr_y is None or abs(w["top"] - curr_y) <= 5.0:
                curr_line.append(w)
                curr_y = w["top"]
            else:
                lines_grouped.append(curr_line)
                curr_line = [w]
                curr_y = w["top"]

        if curr_line:
            lines_grouped.append(curr_line)

        if len(lines_grouped) < 2:
            return None

        y_mid = mid_rule["top"] if mid_rule else (lines_grouped[0][-1]["bottom"] + 2.0)
        header_lines = [l for l in lines_grouped if l[0]["top"] < y_mid]
        data_lines = [l for l in lines_grouped if l[0]["top"] >= y_mid]

        if not header_lines:
            header_lines = [lines_grouped[0]]
            data_lines = lines_grouped[1:]

        # Extract header cells
        header_cells_per_line = [cls._group_words_into_cells(l) for l in header_lines]
        data_cells_per_line = [cls._group_words_into_cells(l) for l in data_lines]

        if not data_cells_per_line:
            return None

        # Determine number of columns from data rows
        col_counts = [len(c) for c in data_cells_per_line]
        num_cols = max(col_counts)

        # Build column bounds from the cells
        col_centers: List[List[float]] = [[] for _ in range(num_cols)]
        for r_cells in data_cells_per_line:
            if len(r_cells) == num_cols:
                for idx, c in enumerate(r_cells):
                    col_centers[idx].append((c["x0"] + c["x1"]) / 2.0)

        # Average column boundaries
        avg_centers = [sum(pts) / len(pts) if pts else (x_min + idx * 80) for idx, pts in enumerate(col_centers)]
        col_bounds = []
        for i in range(num_cols):
            x_l = x_min if i == 0 else (avg_centers[i - 1] + avg_centers[i]) / 2.0
            x_r = x_max if i == num_cols - 1 else (avg_centers[i] + avg_centers[i + 1]) / 2.0
            col_bounds.append((x_l, x_r))

        # Build headers with Spanning-Tree HeaderPath Reconstructor
        header_paths = []
        for c_idx, (x_l, x_r) in enumerate(col_bounds):
            h_texts = []
            col_w = max(10.0, x_r - x_l)
            for h_row in header_cells_per_line:
                # Spanning-tree check: cell center is in column OR cell horizontally overlaps column by >= 30%
                matched = [
                    c["text"] for c in h_row
                    if (x_l <= (c["x0"] + c["x1"]) / 2.0 <= x_r) or
                       (max(0.0, min(x_r, c["x1"]) - max(x_l, c["x0"])) >= 0.3 * col_w)
                ]
                if matched:
                    seen = set()
                    unique_texts = [x for x in matched if not (x in seen or seen.add(x))]
                    h_texts.append(" ".join(unique_texts))
            h_val = " :: ".join(h_texts) if h_texts else f"Kolom_{c_idx+1}"
            header_paths.append(h_val)

        # Build data rows
        structured_rows = []
        for r_idx, d_cells in enumerate(data_cells_per_line):
            row_cells = []
            row_label = d_cells[0]["text"] if d_cells else f"Baris_{r_idx+1}"

            for c_idx, (x_l, x_r) in enumerate(col_bounds):
                matched = [c for c in d_cells if x_l <= (c["x0"] + c["x1"]) / 2.0 <= x_r]
                if matched:
                    raw_val = matched[0]["text"]
                    c_bbox = [round(matched[0]["x0"], 1), round(matched[0]["top"], 1), round(matched[0]["x1"], 1), round(matched[0]["bottom"], 1)]
                else:
                    raw_val = ""
                    c_bbox = [round(x_l, 1), round(d_cells[0]["top"], 1), round(x_r, 1), round(d_cells[0]["bottom"], 1)]

                norm_info = NumberNormalizer.parse_numeric(raw_val)

                cell_dict = {
                    "row": r_idx + 1,
                    "col": c_idx + 1,
                    "row_idx": r_idx,
                    "col_idx": c_idx,
                    "text": raw_val,
                    "raw_val": raw_val,
                    "header_path": header_paths[c_idx],
                    "row_label": row_label,
                    "num_val": norm_info["float_val"] if norm_info else None,
                    "decimals": norm_info["decimals"] if norm_info else 0,
                    "bbox": c_bbox
                }
                row_cells.append(cell_dict)
            structured_rows.append(row_cells)

        caption, table_num, norm_id = cls._detect_table_caption(all_words, [x_min, y_top, x_max, y_bottom])
        t_id = f"Tabel_{norm_id.replace('.', '_')}" if norm_id else (f"Tabel_{table_num}" if table_num else f"Tabel_{page_num}_1")

        return {
            "table_id": t_id,
            "page": page_num,
            "table_num": table_num,
            "normalized_id": norm_id,
            "table_type": cls.classify_table_type(header_paths, structured_rows, caption or ""),
            "y_bottom": round(y_bottom, 1),
            "caption": caption,
            "bbox": [round(x_min, 1), round(y_top, 1), round(x_max, 1), round(y_bottom, 1)],
            "num_rows": len(structured_rows),
            "num_cols": num_cols,
            "header_paths": header_paths,
            "rows": structured_rows
        }

    @classmethod
    def extract_tables_from_pdfplumber_page(
        cls,
        page,
        page_num: int,
        pre_extracted_words: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        # Prioritas 1: Ekstraksi tabel bergaris kotak (seperti tabel SPSS Bab IV)
        tables = page.find_tables()
        extracted_tables = []
        page_words = pre_extracted_words if pre_extracted_words is not None else (page.extract_words() or [])

        for t_idx, table in enumerate(tables):
            raw_data = table.extract()
            if not raw_data or len(raw_data) < 2:
                continue

            table_bbox = list(table.bbox)
            header_row = raw_data[0]
            num_cols = len(header_row)

            # Spanning-tree header reconstruction for nested headers (e.g. parent colspan over sub-headers)
            # Ketat: HANYA jika sel numerik valid <= 1 DAN mengandung kata kunci header
            is_sub = False
            if len(raw_data) > 2:
                is_sub = has_sub_header(raw_data[1], num_cols)

            if is_sub:
                sub_row = raw_data[1]
                header_paths = []
                curr_parent = ""
                for c in range(num_cols):
                    p_val = str(header_row[c]).replace("\n", " ").strip() if c < len(header_row) and header_row[c] else ""
                    if p_val:
                        curr_parent = p_val
                    s_val = str(sub_row[c]).replace("\n", " ").strip() if c < len(sub_row) and sub_row[c] else ""
                    if curr_parent and s_val and curr_parent != s_val:
                        header_paths.append(f"{curr_parent} :: {s_val}")
                    elif s_val:
                        header_paths.append(s_val)
                    elif curr_parent:
                        header_paths.append(curr_parent)
                    else:
                        header_paths.append(f"Kolom_{c+1}")
                start_r_idx = 2
            else:
                header_paths = [str(h).replace("\n", " ").strip() if h else f"Kolom_{c+1}" for c, h in enumerate(header_row)]
                start_r_idx = 1

            structured_rows = []

            table_rows_objs = getattr(table, "rows", [])
            approx_row_height = (table_bbox[3] - table_bbox[1]) / max(1, len(raw_data))
            approx_col_width = (table_bbox[2] - table_bbox[0]) / max(1, num_cols)

            last_valid_row_label = ""
            for r_idx in range(start_r_idx, len(raw_data)):
                row_raw = raw_data[r_idx]
                if not row_raw:
                    continue

                # 1. Multi-line spatial row splitting:
                # Jika >= 2 sel mengandung '\n' dengan pola angka multi-baris, pecah baris tersebut
                multiline_cells = sum(1 for v in row_raw if v and "\n" in str(v))
                if multiline_cells >= 2:
                    split_cols = [str(v).split("\n") if v is not None else [""] for v in row_raw]
                    max_lines = max(len(s) for s in split_cols)
                    if max_lines >= 2:
                        for sub_i in range(max_lines):
                            sub_row_raw = [
                                split_cols[c][sub_i].strip() if sub_i < len(split_cols[c]) else ""
                                for c in range(num_cols)
                            ]
                            c0_text = sub_row_raw[0] if sub_row_raw and sub_row_raw[0] else ""
                            if not c0_text and last_valid_row_label:
                                sub_val = sub_row_raw[1] if len(sub_row_raw) > 1 and sub_row_raw[1] else ""
                                if sub_val and (sub_val.isdigit() or len(sub_val) <= 12):
                                    row_label = f"{last_valid_row_label} :: {sub_val}"
                                else:
                                    row_label = last_valid_row_label
                            elif c0_text:
                                last_valid_row_label = c0_text
                                row_label = c0_text
                            else:
                                row_label = f"Baris_{r_idx}_{sub_i+1}"

                            row_cells = []
                            for c_idx in range(num_cols):
                                raw_val = sub_row_raw[c_idx] if c_idx < len(sub_row_raw) else ""
                                norm_info = NumberNormalizer.parse_numeric(raw_val)
                                cell_dict = {
                                    "row": len(structured_rows) + 1,
                                    "col": c_idx + 1,
                                    "row_idx": len(structured_rows),
                                    "col_idx": c_idx,
                                    "text": raw_val,
                                    "raw_val": raw_val,
                                    "header_path": header_paths[c_idx],
                                    "row_label": row_label,
                                    "num_val": norm_info["float_val"] if norm_info else None,
                                    "decimals": norm_info["decimals"] if norm_info else 0,
                                    "bbox": [
                                        round(table_bbox[0] + c_idx * approx_col_width, 1),
                                        round(table_bbox[1] + r_idx * approx_row_height, 1),
                                        round(table_bbox[0] + (c_idx + 1) * approx_col_width, 1),
                                        round(table_bbox[1] + (r_idx + 1) * approx_row_height, 1)
                                    ]
                                }
                                row_cells.append(cell_dict)
                            structured_rows.append(row_cells)
                        continue

                # 2. Rowspan forward-fill
                c0_text = str(row_raw[0]).replace("\n", " ").strip() if row_raw and row_raw[0] else ""
                if not c0_text and last_valid_row_label:
                    sub_val = str(row_raw[1]).replace("\n", " ").strip() if len(row_raw) > 1 and row_raw[1] else ""
                    if sub_val and (sub_val.isdigit() or len(sub_val) <= 12):
                        row_label = f"{last_valid_row_label} :: {sub_val}"
                    else:
                        row_label = last_valid_row_label
                elif c0_text:
                    last_valid_row_label = c0_text
                    row_label = c0_text
                else:
                    row_label = f"Baris_{r_idx}"

                row_cells = []

                # Get row cell bounding boxes from pdfplumber table.rows if available
                r_cells_objs = table_rows_objs[r_idx].cells if r_idx < len(table_rows_objs) else []

                for c_idx in range(num_cols):
                    raw_val = str(row_raw[c_idx]).strip() if c_idx < len(row_raw) and row_raw[c_idx] is not None else ""
                    norm_info = NumberNormalizer.parse_numeric(raw_val)

                    # Determine exact cell bounding box
                    cell_box = r_cells_objs[c_idx] if c_idx < len(r_cells_objs) else None

                    # If cell_box is valid, search for exact word within cell for ultra-high precision
                    c_bbox = None
                    if cell_box and raw_val:
                        matched_words = [
                            w for w in page_words
                            if (cell_box[0] - 4.0 <= (w["x0"] + w["x1"]) / 2.0 <= cell_box[2] + 4.0 and
                                cell_box[1] - 4.0 <= (w["top"] + w["bottom"]) / 2.0 <= cell_box[3] + 4.0)
                        ]
                        for w in matched_words:
                            if raw_val in w["text"] or w["text"] in raw_val:
                                c_bbox = [round(w["x0"] - 1.5, 1), round(w["top"] - 1.5, 1), round(w["x1"] + 1.5, 1), round(w["bottom"] + 1.5, 1)]
                                break
                        if not c_bbox and matched_words:
                            c_bbox = [
                                round(min(w["x0"] for w in matched_words) - 1.5, 1),
                                round(min(w["top"] for w in matched_words) - 1.5, 1),
                                round(max(w["x1"] for w in matched_words) + 1.5, 1),
                                round(max(w["bottom"] for w in matched_words) + 1.5, 1)
                            ]

                    if not c_bbox:
                        if cell_box:
                            c_bbox = [round(cell_box[0], 1), round(cell_box[1], 1), round(cell_box[2], 1), round(cell_box[3], 1)]
                        else:
                            y0 = table_bbox[1] + (r_idx * approx_row_height)
                            y1 = y0 + approx_row_height
                            x0 = table_bbox[0] + (c_idx * approx_col_width)
                            x1 = x0 + approx_col_width
                            c_bbox = [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]

                    cell_dict = {
                        "row": len(structured_rows) + 1,
                        "col": c_idx + 1,
                        "row_idx": len(structured_rows),
                        "col_idx": c_idx,
                        "text": raw_val,
                        "raw_val": raw_val,
                        "header_path": header_paths[c_idx],
                        "row_label": row_label,
                        "num_val": norm_info["float_val"] if norm_info else None,
                        "decimals": norm_info["decimals"] if norm_info else 0,
                        "bbox": c_bbox
                    }
                    row_cells.append(cell_dict)
                structured_rows.append(row_cells)

            caption, table_num, norm_id = cls._detect_table_caption(page_words, table_bbox)
            t_id = f"Tabel_{norm_id.replace('.', '_')}" if norm_id else (f"Tabel_{table_num}" if table_num else f"Tabel_{page_num}_{t_idx+1}")

            extracted_tables.append({
                "table_id": t_id,
                "page": page_num,
                "table_num": table_num,
                "normalized_id": norm_id,
                "table_type": cls.classify_table_type(header_paths, structured_rows, caption or ""),
                "y_bottom": round(table_bbox[3], 1) if len(table_bbox) >= 4 else 0.0,
                "caption": caption,
                "bbox": [round(b, 1) for b in table_bbox],
                "num_rows": len(structured_rows),
                "num_cols": num_cols,
                "header_paths": header_paths,
                "rows": structured_rows
            })

        # Union Multi-Table: Kumpulkan dari find_tables() DAN extract_3line_table()
        candidate_tables = list(extracted_tables)
        table_3line = cls.extract_3line_table(page, page_num, pre_extracted_words=page_words)
        if table_3line and table_3line.get("num_rows", 0) >= 1 and table_3line.get("num_cols", 0) >= 2:
            box_3l = table_3line.get("bbox", [0, 0, 0, 0])
            matched_dup = False
            for idx_e, ex in enumerate(candidate_tables):
                box_ex = ex.get("bbox", [0, 0, 0, 0])
                if len(box_3l) >= 4 and len(box_ex) >= 4:
                    xA = max(box_3l[0], box_ex[0])
                    yA = max(box_3l[1], box_ex[1])
                    xB = min(box_3l[2], box_ex[2])
                    yB = min(box_3l[3], box_ex[3])
                    inter = max(0.0, xB - xA) * max(0.0, yB - yA)
                    area1 = max(1.0, (box_3l[2] - box_3l[0]) * (box_3l[3] - box_3l[1]))
                    area2 = max(1.0, (box_ex[2] - box_ex[0]) * (box_ex[3] - box_ex[1]))
                    iou = inter / (area1 + area2 - inter) if (area1 + area2 - inter) > 0 else 0.0
                    if iou >= 0.5:
                        matched_dup = True
                        score_3l = table_3line.get("num_rows", 0) * 10 + sum(1 for r in table_3line.get("rows", []) for c in r if c.get("num_val") is not None)
                        score_ex = ex.get("num_rows", 0) * 10 + sum(1 for r in ex.get("rows", []) for c in r if c.get("num_val") is not None)
                        if score_3l > score_ex:
                            candidate_tables[idx_e] = table_3line
                        break
            if not matched_dup:
                candidate_tables.append(table_3line)

        # Urutkan seluruh tabel dari atas ke bawah (y0)
        candidate_tables.sort(key=lambda t: t.get("bbox", [0, 0, 0, 0])[1] if len(t.get("bbox", [])) >= 4 else 0.0)
        return candidate_tables

    @staticmethod
    def stitch_cross_page_tables(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(tables) <= 1:
            return tables

        stitched: List[Dict[str, Any]] = []
        skip_indices = set()

        for i in range(len(tables)):
            if i in skip_indices:
                continue
            curr = tables[i]
            if i + 1 < len(tables):
                nxt = tables[i + 1]
                if nxt.get("page") == curr.get("page", 0) + 1 and nxt.get("num_cols") == curr.get("num_cols"):
                    curr_bbox = curr.get("bbox", [0, 0, 0, 0])
                    nxt_bbox = nxt.get("bbox", [0, 0, 0, 0])
                    if len(curr_bbox) >= 4 and len(nxt_bbox) >= 4:
                        dx0 = abs(nxt_bbox[0] - curr_bbox[0])
                        dx1 = abs(nxt_bbox[2] - curr_bbox[2])
                        if dx0 <= 8.0 and dx1 <= 8.0:
                            merged_rows = list(curr.get("rows", []))
                            offset = len(merged_rows)
                            for r_idx, r in enumerate(nxt.get("rows", [])):
                                if isinstance(r, list):
                                    for c_idx, cell in enumerate(r):
                                        if isinstance(cell, dict):
                                            cell["row"] = cell.get("row", r_idx + 1) + offset
                                            cell["row_idx"] = cell.get("row_idx", r_idx) + offset
                                            if "col" not in cell:
                                                cell["col"] = c_idx + 1
                                            if "col_idx" not in cell:
                                                cell["col_idx"] = c_idx
                                            if "text" not in cell and "raw_val" in cell:
                                                cell["text"] = cell["raw_val"]
                                            elif "raw_val" not in cell and "text" in cell:
                                                cell["raw_val"] = cell["text"]
                                        elif isinstance(cell, str):
                                            r[c_idx] = {
                                                "row": r_idx + 1 + offset,
                                                "row_idx": r_idx + offset,
                                                "col": c_idx + 1,
                                                "col_idx": c_idx,
                                                "text": cell,
                                                "raw_val": cell,
                                                "bbox": [0, 0, 0, 0]
                                            }
                                merged_rows.append(r)

                            merged_table = dict(curr)
                            merged_table["rows"] = merged_rows
                            merged_table["num_rows"] = len(merged_rows)
                            merged_table["is_cross_page"] = True
                            merged_table["stitched_pages"] = [curr.get("page", 1), nxt.get("page", 1)]
                            stitched.append(merged_table)
                            skip_indices.add(i + 1)
                            continue

            stitched.append(curr)

        return stitched
