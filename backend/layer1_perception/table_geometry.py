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
    "total", "df", "p-value", "keterangan", "variabel", "variable",
    "b", "beta", "error", "unstandardized", "standardized", "coefficients",
    "tolerance", "vif", "collinearity", "statistics", "model", "pearson",
    "spearman", "asymp", "exact", "lower", "upper", "bound", "confidence",
    "interval", "sum", "squares", "kurtosis", "skewness", "statistic",
    "p", "value", "se", "cumulative", "r", "square", "deviation"
}

STANDALONE_STAT_CHILDREN = {
    "t", "f", "z", "sig", "sig.", "df", "p", "p-value", "p value",
    "prob", "prob.", "tolerance", "vif", "n"
}

SINGLE_COL_PARENTS = {
    "model", "variabel", "variable", "no", "no.", "keterangan",
    "kategori", "item", "indikator", "faktor", "metode", "method"
}


def _norm_cell_ws(text: str) -> str:
    """Normalizes NBSP, zero-width spaces, and repeated whitespace for strict cell-word comparison."""
    if not text:
        return ""
    cleaned = text.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_numeric_cell_token(tok: str) -> bool:
    """Returns True if token looks like a numeric value (including negative/leading-dot/asterisk)."""
    t = _norm_cell_ws(tok).replace("\u2212", "-").replace("\u2013", "-")
    if not t:
        return False
    return bool(
        re.match(
            r"^[+-]?(?:\d{1,3}(?:[.,]\d{3})*|\d+)(?:[.,]\d+)?%?[*†‡a-z]?$|^[+-]?[.,]\d+%?[*†‡a-z]?$",
            t,
            re.IGNORECASE,
        )
    )


def is_text_label(val: Any) -> bool:
    """
    Checks if a cell text is a descriptive text label (e.g. 'Kelas Kontrol', 'Skala Awal')
    rather than purely numeric, percentage, dash, or empty symbol.
    """
    if val is None:
        return False
    v = str(val).strip()
    if not v or v in ("-", "--", "---", "/", ".", "NA", "N/A", "None", "NaN"):
        return False
    # Reject pure numbers, decimals, percentages, or statistics with letter footnotes (e.g. 19, 80.00, .171, -.123, 74,03%, .144c)
    if re.match(r"^[<>]?\s*[+-]?(?:\d{1,3}(?:[.,]\d{3})*|\d+)(?:[.,]\d+)?\s*%?[a-z]?$", v, re.IGNORECASE):
        return False
    # Must contain at least one word with 2+ alphabetic letters
    return bool(re.search(r"[a-zA-Z]{2,}", v))


def has_sub_header(sub_row: List[Any], num_cols: Optional[int] = None) -> bool:
    """
    Checks if a row is a sub-header row.
    STRICT:
    - Never True if any cell contains decimal numeric values (e.g. 0,804).
    - Valid numeric cells count is <= 1 (if cols >= 5 and integer-only) or 0.
    - Matches whole words for header keywords (never substring single-letters like 'n' or 't').
    """
    if not sub_row:
        return False
    # If any cell contains a decimal number, it is definitely a data row, not a header!
    for v in sub_row:
        if v:
            parsed = NumberNormalizer.parse_numeric(str(v))
            if parsed and parsed.get("decimals", 0) > 0:
                return False

    if num_cols is None:
        num_cols = len(sub_row)
    num_numeric = sum(1 for v in sub_row if v and NumberNormalizer.parse_numeric(str(v)) is not None)
    max_allowed_num = 1 if num_cols >= 5 else 0
    if num_numeric <= max_allowed_num:
        has_kw = any(
            any(kw in set(re.findall(r"\b[a-zA-Z]+\b", str(v).lower())) for kw in HEADER_KEYWORDS)
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
    def _group_words_into_cells(
        words: List[Dict[str, Any]],
        max_word_gap: float = 12.0,
        numeric_word_gap: float = 6.0,
    ) -> List[Dict[str, Any]]:
        """
        Groups words on the same line into cells based on horizontal spacing.
        Uses a tighter numeric_word_gap (default 6pt) whenever either adjacent token is numeric
        so negative values (e.g. '-0,412') in borderless 3-line APA tables never merge into neighbor columns.
        """
        if not words:
            return []
        words = sorted(words, key=lambda w: float(w["x0"]))
        cells: List[Dict[str, Any]] = []
        curr = [words[0]]

        def _flush(group: List[Dict[str, Any]]) -> Dict[str, Any]:
            parts: List[str] = []
            for idx_g, item in enumerate(group):
                txt = str(item["text"])
                if (
                    idx_g > 0
                    and parts
                    and parts[-1] in ("-", "\u2212", "\u2013", "+")
                    and re.match(r"^[0-9.,]", txt)
                ):
                    parts[-1] = ("-" if parts[-1] in ("-", "\u2212", "\u2013") else "+") + txt
                else:
                    parts.append(txt)
            cell_text = " ".join(parts).strip()
            return {
                "text": cell_text,
                "x0": float(group[0]["x0"]),
                "x1": float(group[-1]["x1"]),
                "top": min(float(x["top"]) for x in group),
                "bottom": max(float(x["bottom"]) for x in group),
            }

        for w in words[1:]:
            prev_w = curr[-1]
            gap = float(w["x0"]) - float(prev_w["x1"])
            prev_txt = str(prev_w["text"]).strip()
            next_txt = str(w["text"]).strip()

            # Keep detached unary minus glued to its number if right next to it (<= 4pt)
            if prev_txt in ("-", "\u2212", "\u2013", "+") and re.match(r"^[0-9.,]", next_txt) and gap <= 4.0:
                curr.append(w)
                continue

            # Tighter x_tolerance across numeric boundaries so adjacent numeric columns stay separate
            if _is_numeric_cell_token(prev_txt) or _is_numeric_cell_token(next_txt):
                threshold = numeric_word_gap
            else:
                threshold = max_word_gap

            if gap <= threshold:
                curr.append(w)
            else:
                cells.append(_flush(curr))
                curr = [w]

        if curr:
            cells.append(_flush(curr))

        return cells

    @staticmethod
    def flatten_multitier_headers(
        raw_data: List[List[Any]],
        table_rows_objs: Optional[List[Any]] = None,
    ) -> Tuple[List[str], int]:
        """
        Deterministically flattens 1-tier, 2-tier, or 3-tier merged SPSS table headers
        by forward-filling None parent cells strictly across their grouped child columns.
        Returns (header_paths, start_data_row_idx).
        """
        if not raw_data:
            return [], 0
        num_cols = max(len(r) for r in raw_data if r) if any(raw_data) else 0
        if num_cols == 0:
            return [], 0

        # Detect how many leading rows are header tiers (1..3, leaving >= 1 data row)
        header_row_count = 1
        max_header_tiers = min(3, max(1, len(raw_data) - 1))
        for r_i in range(1, max_header_tiers):
            if has_sub_header(raw_data[r_i], num_cols):
                header_row_count = r_i + 1
            else:
                break

        if header_row_count == 1:
            row0 = raw_data[0]
            paths = [
                _norm_cell_ws(str(row0[c]).replace("\n", " "))
                if c < len(row0) and row0[c] is not None and _norm_cell_ws(str(row0[c]))
                else f"Kolom_{c+1}"
                for c in range(num_cols)
            ]
            return paths, 1

        # Build cleaned header matrix [tier][col]
        tiers: List[List[str]] = []
        for r_i in range(header_row_count):
            row = raw_data[r_i]
            tiers.append([
                _norm_cell_ws(str(row[c]).replace("\n", " "))
                if c < len(row) and row[c] is not None
                else ""
                for c in range(num_cols)
            ])

        # Forward-fill grouped parent cells across None/empty slots in upper tiers
        filled_tiers = [list(t) for t in tiers]
        for r_i in range(header_row_count - 1):
            # Optional pdfplumber cell rects for exact geometric span checking
            r_cells = None
            if table_rows_objs and r_i < len(table_rows_objs):
                r_cells = getattr(table_rows_objs[r_i], "cells", None)

            curr_parent = ""
            curr_parent_x1: Optional[float] = None
            parent_consumed_beta = False
            for c in range(num_cols):
                val = filled_tiers[r_i][c]
                if val:
                    curr_parent = val
                    parent_consumed_beta = False
                    if r_cells and c < len(r_cells) and r_cells[c]:
                        curr_parent_x1 = float(r_cells[c][2])
                    else:
                        curr_parent_x1 = None
                    # Check if this column already has child "beta"
                    lower_vals = [filled_tiers[k][c].lower() for k in range(r_i + 1, header_row_count) if filled_tiers[k][c]]
                    if any("beta" in lv for lv in lower_vals):
                        parent_consumed_beta = True
                    continue

                # Slot is empty in tier r_i: decide whether to forward-fill curr_parent
                if not curr_parent:
                    continue

                lower_vals = [filled_tiers[k][c] for k in range(r_i + 1, header_row_count) if filled_tiers[k][c]]
                if not lower_vals:
                    # No child label beneath this empty slot -> do not smear parent
                    continue

                p_low = curr_parent.lower()
                child_low = lower_vals[0].lower()

                # Never forward-fill single-column stub headers like Model / Variabel / No
                if p_low in SINGLE_COL_PARENTS:
                    continue

                # In SPSS Coefficients, 'Standardized Coefficients' only spans 'Beta' (1 column);
                # trailing standalone stats ('t', 'Sig.') must NOT inherit 'Standardized Coefficients'.
                if "standardized" in p_low and "unstandardized" not in p_low and (
                    parent_consumed_beta or child_low in STANDALONE_STAT_CHILDREN
                ):
                    curr_parent = ""
                    continue

                # If child is a standalone top-level statistic (e.g. 't', 'Sig.') and parent is a specific
                # coefficient group (not a table-wide banner like 'Descriptive Statistics'), do not bleed parent.
                if child_low in STANDALONE_STAT_CHILDREN and "coefficient" in p_low:
                    curr_parent = ""
                    continue

                # If pdfplumber geometric cell rects exist for row r_i+1 and show this column is past curr_parent_x1,
                # stop forward-filling.
                if curr_parent_x1 is not None and table_rows_objs and (r_i + 1) < len(table_rows_objs):
                    child_cells = getattr(table_rows_objs[r_i + 1], "cells", None)
                    if child_cells and c < len(child_cells) and child_cells[c]:
                        child_cx = 0.5 * (float(child_cells[c][0]) + float(child_cells[c][2]))
                        if child_cx > curr_parent_x1 + 3.0:
                            curr_parent = ""
                            continue

                filled_tiers[r_i][c] = curr_parent
                if any("beta" in lv.lower() for lv in lower_vals):
                    parent_consumed_beta = True

        header_paths: List[str] = []
        for c in range(num_cols):
            parts: List[str] = []
            for r_i in range(header_row_count):
                seg = filled_tiers[r_i][c]
                if seg and (not parts or parts[-1].lower() != seg.lower()):
                    parts.append(seg)
            header_paths.append(" :: ".join(parts) if parts else f"Kolom_{c+1}")

        return header_paths, header_row_count

    @staticmethod
    def _cluster_table_bounds_from_words(
        table_words: List[Dict[str, Any]],
        table_bbox: List[float],
        num_rows: int,
        num_cols: int,
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        """
        C6: Derives uneven column X-bounds and row Y-bounds via word coordinate clustering
        when pdfplumber cell_box rectangles are missing.
        """
        if not table_words or num_cols <= 0 or num_rows <= 0:
            return [], []

        tx0, ty0, tx1, ty1 = [float(v) for v in table_bbox[:4]]

        # 1. Y-clustering into visual rows
        y_sorted = sorted(table_words, key=lambda w: 0.5 * (float(w["top"]) + float(w["bottom"])))
        y_clusters: List[List[Dict[str, Any]]] = []
        for w in y_sorted:
            wy = 0.5 * (float(w["top"]) + float(w["bottom"]))
            wh = max(4.0, float(w["bottom"]) - float(w["top"]))
            if not y_clusters:
                y_clusters.append([w])
            else:
                prev_mean_y = sum(0.5 * (float(x["top"]) + float(x["bottom"])) for x in y_clusters[-1]) / len(y_clusters[-1])
                if abs(wy - prev_mean_y) <= max(4.5, 0.5 * wh):
                    y_clusters[-1].append(w)
                else:
                    y_clusters.append([w])

        row_bounds: List[Tuple[float, float]] = []
        for cl in y_clusters:
            r_top = max(ty0, min(float(w["top"]) for w in cl))
            r_bot = min(ty1, max(float(w["bottom"]) for w in cl))
            if r_bot > r_top:
                row_bounds.append((r_top, r_bot))

        # 2. X-clustering into columns using cell grouping across all visual rows
        col_centers: List[List[float]] = [[] for _ in range(num_cols)]
        for cl in y_clusters:
            grouped = TableGeometryExtractor._group_words_into_cells(cl)
            if len(grouped) == num_cols:
                for idx_c, gc in enumerate(grouped):
                    col_centers[idx_c].append(0.5 * (gc["x0"] + gc["x1"]))

        if all(col_centers):
            avg_x = [sum(pts) / len(pts) for pts in col_centers]
            col_bounds: List[Tuple[float, float]] = []
            for i in range(num_cols):
                xl = tx0 if i == 0 else 0.5 * (avg_x[i - 1] + avg_x[i])
                xr = tx1 if i == num_cols - 1 else 0.5 * (avg_x[i] + avg_x[i + 1])
                col_bounds.append((xl, xr))
        else:
            # Fallback: 1D gap clustering on all word x-intervals
            intervals = sorted((float(w["x0"]), float(w["x1"])) for w in table_words)
            merged: List[List[float]] = []
            for ix0, ix1 in intervals:
                if not merged or ix0 > merged[-1][1] + 5.0:
                    merged.append([ix0, ix1])
                else:
                    merged[-1][1] = max(merged[-1][1], ix1)
            if len(merged) == num_cols:
                col_bounds = []
                for i in range(num_cols):
                    xl = tx0 if i == 0 else 0.5 * (merged[i - 1][1] + merged[i][0])
                    xr = tx1 if i == num_cols - 1 else 0.5 * (merged[i][1] + merged[i + 1][0])
                    col_bounds.append((xl, xr))
            else:
                col_bounds = []

        return col_bounds, row_bounds

    @staticmethod
    def _resolve_cell_bbox_strict(
        cell_box: Optional[Tuple[float, float, float, float]],
        raw_val: str,
        norm_info: Optional[Dict[str, Any]],
        page_words: List[Dict[str, Any]],
        clustered_col_bounds: List[Tuple[float, float]],
        clustered_row_bounds: List[Tuple[float, float]],
        raw_row_idx: int,
        col_idx: int,
        table_bbox: List[float],
        approx_col_width: float,
        approx_row_height: float,
    ) -> Tuple[List[float], bool]:
        """
        C5 & C6: Resolves exact cell bounding box.
        - When cell_box exists: requires word center strictly inside cell_box (0pt padding),
          matching by whitespace/NBSP-normalized text equality or parsed numeric equality.
          Never steals words from neighboring cells; falls back to full cell_box.
        - When cell_box is missing: derives bounds from X/Y word clustering before
          resorting to uniform grid (marked bbox_approx=True).
        """
        def _match_inside(box: Tuple[float, float, float, float]) -> Optional[List[float]]:
            bx0, by0, bx1, by1 = float(box[0]), float(box[1]), float(box[2]), float(box[3])
            if bx1 <= bx0 or by1 <= by0:
                return None
            inside_words = [
                w for w in page_words
                if (bx0 <= 0.5 * (float(w["x0"]) + float(w["x1"])) <= bx1 and
                    by0 <= 0.5 * (float(w["top"]) + float(w["bottom"])) <= by1)
            ]
            if not inside_words or not raw_val:
                return None

            target_ws = _norm_cell_ws(raw_val)
            target_num = norm_info["float_val"] if norm_info is not None else None

            # 1. Exact single-word normalized text match strictly inside cell_box
            for w in inside_words:
                if _norm_cell_ws(w["text"]) == target_ws:
                    return [
                        round(max(bx0, float(w["x0"])), 1),
                        round(max(by0, float(w["top"])), 1),
                        round(min(bx1, float(w["x1"])), 1),
                        round(min(by1, float(w["bottom"])), 1),
                    ]

            # 2. Numeric value equality match (handles '2,67' vs '2,670' or Indonesian '1.450,25')
            if target_num is not None:
                for w in inside_words:
                    wp = NumberNormalizer.parse_numeric(w["text"])
                    if wp is not None and abs(wp["float_val"] - target_num) <= 1e-6:
                        return [
                            round(max(bx0, float(w["x0"])), 1),
                            round(max(by0, float(w["top"])), 1),
                            round(min(bx1, float(w["x1"])), 1),
                            round(min(by1, float(w["bottom"])), 1),
                        ]

            # 3. Multi-word cell text exact normalized match using ONLY words strictly inside cell_box
            sorted_in = sorted(inside_words, key=lambda w: (float(w["top"]), float(w["x0"])))
            joined_ws = _norm_cell_ws(" ".join(w["text"] for w in sorted_in))
            if joined_ws == target_ws:
                return [
                    round(max(bx0, min(float(w["x0"]) for w in sorted_in)), 1),
                    round(max(by0, min(float(w["top"]) for w in sorted_in)), 1),
                    round(min(bx1, max(float(w["x1"]) for w in sorted_in)), 1),
                    round(min(by1, max(float(w["bottom"]) for w in sorted_in)), 1),
                ]

            return None

        # Path 1: Vector cell_box provided by pdfplumber
        if cell_box and len(cell_box) >= 4 and float(cell_box[2]) > float(cell_box[0]) and float(cell_box[3]) > float(cell_box[1]):
            matched_rect = _match_inside(cell_box)
            if matched_rect and matched_rect[2] > matched_rect[0] and matched_rect[3] > matched_rect[1]:
                return matched_rect, False
            return [
                round(float(cell_box[0]), 1),
                round(float(cell_box[1]), 1),
                round(float(cell_box[2]), 1),
                round(float(cell_box[3]), 1),
            ], False

        # Path 2: C6 word-clustered column/row bounds fallback
        if col_idx < len(clustered_col_bounds) and raw_row_idx < len(clustered_row_bounds):
            cx0, cx1 = clustered_col_bounds[col_idx]
            ry0, ry1 = clustered_row_bounds[raw_row_idx]
            if cx1 > cx0 and ry1 > ry0:
                matched_rect = _match_inside((cx0, ry0, cx1, ry1))
                if matched_rect and matched_rect[2] > matched_rect[0] and matched_rect[3] > matched_rect[1]:
                    return matched_rect, False
                return [round(cx0, 1), round(ry0, 1), round(cx1, 1), round(ry1, 1)], True

        # Path 3: Last-resort uniform grid (flagged bbox_approx=True)
        y0 = float(table_bbox[1]) + (raw_row_idx * approx_row_height)
        y1 = y0 + approx_row_height
        x0 = float(table_bbox[0]) + (col_idx * approx_col_width)
        x1 = x0 + approx_col_width
        return [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)], True

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

        matches = list(re.finditer(r"\b(Tabel\s+([IVX]+|\d+)(?:\s*[.\-]\s*(\d+))?[\.\:\s]*(?:(?!\bTabel\b)[^\r\n])*)", above_text, re.IGNORECASE))
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
        last_valid_row_label = ""
        parent_group = ""
        for r_idx, d_cells in enumerate(data_cells_per_line):
            row_cells = []
            if col_bounds:
                c0_cells = [c for c in d_cells if col_bounds[0][0] <= (c["x0"] + c["x1"]) / 2.0 <= col_bounds[0][1]]
                c1_cells = [c for c in d_cells if len(col_bounds) > 1 and col_bounds[1][0] <= (c["x0"] + c["x1"]) / 2.0 <= col_bounds[1][1]]
                c0_text = c0_cells[0]["text"].replace("\n", " ").strip() if c0_cells else ""
                c1_text = c1_cells[0]["text"].replace("\n", " ").strip() if c1_cells else ""
            else:
                c0_text = d_cells[0]["text"].replace("\n", " ").strip() if d_cells and len(d_cells) > 0 else ""
                c1_text = d_cells[1]["text"].replace("\n", " ").strip() if d_cells and len(d_cells) > 1 else ""

            is_total_row = any(w in c0_text.lower() or w in c1_text.lower() for w in ("total", "jumlah", "total responden", "sum"))

            # 1. Vertical forward-fill kolom 0
            if is_text_label(c0_text) and not is_total_row:
                parent_group = c0_text
            elif not c0_text and parent_group and not is_total_row:
                c0_text = parent_group

            is_c1_label = is_text_label(c1_text) and not is_total_row

            # 2. Composite row label jika kolom 1 juga label teks non-numerik yang berbeda
            if is_c1_label and c0_text and c1_text.lower() != c0_text.lower():
                row_label = f"{c0_text} - {c1_text}"
                last_valid_row_label = row_label
            elif is_c1_label:
                row_label = c1_text or c0_text or f"Baris_{r_idx+1}"
                last_valid_row_label = row_label
            elif is_total_row:
                row_label = c1_text if ("total" in c1_text.lower() or "jumlah" in c1_text.lower()) else (c0_text or "Total")
                last_valid_row_label = row_label
            elif c0_text:
                last_valid_row_label = c0_text
                row_label = c0_text
            elif last_valid_row_label:
                row_label = last_valid_row_label
            else:
                row_label = f"Baris_{r_idx+1}"

            row_label = _norm_cell_ws(row_label.replace("\n", " "))

            for c_idx, (x_l, x_r) in enumerate(col_bounds):
                matched = [c for c in d_cells if x_l <= (c["x0"] + c["x1"]) / 2.0 <= x_r]
                if matched:
                    raw_val = matched[0]["text"]
                    c_bbox = [round(matched[0]["x0"], 1), round(matched[0]["top"], 1), round(matched[0]["x1"], 1), round(matched[0]["bottom"], 1)]
                else:
                    raw_val = c0_text if c_idx == 0 and c0_text else ""
                    c_bbox = [round(x_l, 1), round(d_cells[0]["top"], 1), round(x_r, 1), round(d_cells[0]["bottom"], 1)]

                norm_info = NumberNormalizer.parse_numeric(
                    raw_val,
                    header_context=header_paths[c_idx],
                )

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
                    "bbox": c_bbox,
                    "cell_rect": c_bbox,
                    "bbox_approx": not bool(matched)
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
            table_rows_objs = getattr(table, "rows", [])

            # Deterministic multi-tier SPSS header flattening (forward-filling None cells across grouped headers)
            header_paths, start_r_idx = cls.flatten_multitier_headers(raw_data, table_rows_objs=table_rows_objs)

            structured_rows = []

            approx_row_height = (table_bbox[3] - table_bbox[1]) / max(1, len(raw_data))
            approx_col_width = (table_bbox[2] - table_bbox[0]) / max(1, num_cols)

            # Precompute word-clustered column/row bounds inside table_bbox for C6 fallback when cell_box is missing
            table_inner_words = [
                w for w in page_words
                if (table_bbox[0] <= 0.5 * (float(w["x0"]) + float(w["x1"])) <= table_bbox[2] and
                    table_bbox[1] <= 0.5 * (float(w["top"]) + float(w["bottom"])) <= table_bbox[3])
            ]
            clustered_col_bounds, clustered_row_bounds = cls._cluster_table_bounds_from_words(
                table_inner_words, table_bbox, len(raw_data), num_cols
            )

            # Detect locale per column for context-aware SPSS vs PUEBI parsing
            col_locales = []
            for c_i in range(num_cols):
                col_vals = [
                    str(raw_data[r_i][c_i])
                    for r_i in range(start_r_idx, len(raw_data))
                    if raw_data[r_i] and c_i < len(raw_data[r_i]) and raw_data[r_i][c_i] is not None
                ]
                col_locales.append(NumberNormalizer.detect_column_locale(col_vals))

            table_header_ctx = " ".join(header_paths)

            last_valid_row_label = ""
            parent_group = ""
            sub_parent_group = ""
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
                            c1_text = sub_row_raw[1] if len(sub_row_raw) > 1 and sub_row_raw[1] else ""

                            is_total_sub = any(w in c0_text.lower() or w in c1_text.lower() for w in ("total", "jumlah", "total responden", "sum"))

                            # 1. Vertical forward-fill kolom 0
                            if is_text_label(c0_text) and not is_total_sub:
                                parent_group = c0_text
                            elif not c0_text and parent_group and not is_total_sub:
                                c0_text = parent_group

                            is_c1_sub_label = is_text_label(c1_text) and not is_total_sub

                            # 2. Composite row label jika kolom 1 juga label teks non-numerik yang berbeda
                            if is_c1_sub_label and c0_text and c1_text.lower() != c0_text.lower():
                                row_label = f"{c0_text} - {c1_text}"
                                last_valid_row_label = row_label
                            elif is_c1_sub_label:
                                row_label = c1_text or c0_text or f"Baris_{r_idx}_{sub_i+1}"
                                last_valid_row_label = row_label
                            elif is_total_sub:
                                row_label = c1_text if ("total" in c1_text.lower() or "jumlah" in c1_text.lower()) else (c0_text or "Total")
                                last_valid_row_label = row_label
                            elif c0_text:
                                last_valid_row_label = c0_text
                                row_label = c0_text
                            elif last_valid_row_label:
                                row_label = last_valid_row_label
                            else:
                                row_label = f"Baris_{r_idx}_{sub_i+1}"

                            row_label = _norm_cell_ws(row_label.replace("\n", " "))

                            row_cells = []
                            r_cells_objs_ml = table_rows_objs[r_idx].cells if r_idx < len(table_rows_objs) else []
                            for c_idx in range(num_cols):
                                raw_val = sub_row_raw[c_idx] if c_idx < len(sub_row_raw) else ""
                                if c_idx == 0 and not raw_val and c0_text:
                                    raw_val = c0_text
                                norm_info = NumberNormalizer.parse_numeric(
                                    raw_val,
                                    column_locale=col_locales[c_idx] if c_idx < len(col_locales) else None,
                                    header_context=header_paths[c_idx],
                                    table_context=table_header_ctx,
                                )
                                ml_cell_box = r_cells_objs_ml[c_idx] if c_idx < len(r_cells_objs_ml) else None
                                c_bbox_ml, is_approx_ml = cls._resolve_cell_bbox_strict(
                                    cell_box=ml_cell_box,
                                    raw_val=raw_val,
                                    norm_info=norm_info,
                                    page_words=table_inner_words,
                                    clustered_col_bounds=clustered_col_bounds,
                                    clustered_row_bounds=clustered_row_bounds,
                                    raw_row_idx=r_idx,
                                    col_idx=c_idx,
                                    table_bbox=table_bbox,
                                    approx_col_width=approx_col_width,
                                    approx_row_height=approx_row_height,
                                )
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
                                    "bbox": c_bbox_ml,
                                    "cell_rect": c_bbox_ml,
                                    "bbox_approx": is_approx_ml
                                }
                                row_cells.append(cell_dict)
                            structured_rows.append(row_cells)
                        continue

                # 2. Rowspan forward-fill & composite label
                c0_text = str(row_raw[0]).replace("\n", " ").strip() if row_raw and row_raw[0] else ""
                c1_text = str(row_raw[1]).replace("\n", " ").strip() if len(row_raw) > 1 and row_raw[1] else ""
                c2_text = str(row_raw[2]).replace("\n", " ").strip() if len(row_raw) > 2 and row_raw[2] else ""

                is_empty_row = not any(str(c).strip() for c in row_raw if c is not None)
                is_total_row = any(w in c0_text.lower() or w in c1_text.lower() or w in c2_text.lower() for w in ("total", "jumlah", "total responden", "sum"))

                # 1. Vertical forward-fill kolom 0 dan kolom 1 (merged vertical cells)
                if is_text_label(c0_text) and not is_total_row:
                    if parent_group != c0_text:
                        sub_parent_group = ""
                    parent_group = c0_text
                elif not c0_text and parent_group and not is_total_row:
                    c0_text = parent_group

                if is_text_label(c1_text) and not is_total_row:
                    sub_parent_group = c1_text
                elif not c1_text and sub_parent_group and not is_total_row:
                    c1_text = sub_parent_group

                # 2. Composite row label jika ada label teks non-numerik di kolom 1 atau kolom 2
                label_parts = []
                for txt in (c0_text, c1_text, c2_text):
                    if is_text_label(txt) and not is_total_row:
                        if not any(txt.lower() == p.lower() for p in label_parts):
                            label_parts.append(txt)

                if len(label_parts) >= 2:
                    row_label = " - ".join(label_parts)
                    last_valid_row_label = row_label
                elif len(label_parts) == 1:
                    row_label = label_parts[0]
                    last_valid_row_label = row_label
                elif is_total_row:
                    row_label = c1_text if ("total" in c1_text.lower() or "jumlah" in c1_text.lower()) else (c0_text or "Total")
                    last_valid_row_label = row_label
                elif last_valid_row_label:
                    sub_val = c1_text or c2_text
                    # Jangan awali variabel regresi dengan nomor model numerik SPSS ('1 :: OPM' -> 'OPM')
                    last_is_model_stub = bool(re.match(r"^(?:\d+|valid|missing|model)$", last_valid_row_label.strip(), re.IGNORECASE))
                    if sub_val and last_is_model_stub:
                        row_label = sub_val
                    elif sub_val and (sub_val.isdigit() or len(sub_val) <= 12):
                        row_label = f"{last_valid_row_label} :: {sub_val}"
                    else:
                        row_label = last_valid_row_label
                else:
                    row_label = f"Baris_{r_idx}"

                row_label = _norm_cell_ws(row_label.replace("\n", " "))

                row_cells = []

                # Get row cell bounding boxes from pdfplumber table.rows if available
                r_cells_objs = table_rows_objs[r_idx].cells if r_idx < len(table_rows_objs) else []

                for c_idx in range(num_cols):
                    raw_val = str(row_raw[c_idx]).strip() if c_idx < len(row_raw) and row_raw[c_idx] is not None else ""
                    if c_idx == 0 and not raw_val and c0_text:
                        raw_val = c0_text
                    norm_info = NumberNormalizer.parse_numeric(
                        raw_val,
                        column_locale=col_locales[c_idx] if c_idx < len(col_locales) else None,
                        header_context=header_paths[c_idx],
                        table_context=table_header_ctx,
                    )

                    # Determine exact cell bounding box strictly inside cell_box (C5) or via word clustering (C6)
                    cell_box = r_cells_objs[c_idx] if c_idx < len(r_cells_objs) else None
                    c_bbox, is_bbox_approx = cls._resolve_cell_bbox_strict(
                        cell_box=cell_box,
                        raw_val=raw_val,
                        norm_info=norm_info,
                        page_words=table_inner_words,
                        clustered_col_bounds=clustered_col_bounds,
                        clustered_row_bounds=clustered_row_bounds,
                        raw_row_idx=r_idx,
                        col_idx=c_idx,
                        table_bbox=table_bbox,
                        approx_col_width=approx_col_width,
                        approx_row_height=approx_row_height,
                    )

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
                        "bbox": c_bbox,
                        "cell_rect": c_bbox,
                        "bbox_approx": is_bbox_approx
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
        """
        Stitches genuinely split multi-page tables across consecutive pages (page N -> page N+1)
        while strictly refusing to merge two independent tables that happen to share margins
        and column counts (e.g. sequential SPSS Likert tables in Bab IV).
        """
        if len(tables) <= 1:
            return tables

        def _row_has_terminal_total(rows_list: List[Any]) -> bool:
            if not rows_list:
                return False
            # Inspect the last non-empty row
            for r in reversed(rows_list):
                if not isinstance(r, list) or not r:
                    continue
                texts = []
                for c in r[:3]:
                    if isinstance(c, dict):
                        t = str(c.get("raw_val") or c.get("text") or c.get("row_label") or "").strip().lower()
                    else:
                        t = str(c or "").strip().lower()
                    if t:
                        texts.append(t)
                if not texts:
                    continue
                joined = " ".join(texts)
                return bool(
                    re.search(r"\b(?:total|jumlah|grand\s+total|total\s+responden|keseluruhan)\b", joined)
                )
            return False

        def _is_distinct_next_table(curr_t: Dict[str, Any], nxt_t: Dict[str, Any]) -> bool:
            nxt_cap = str(nxt_t.get("caption") or "").strip()
            is_cont_cap = bool(re.search(r"\b(?:lanjutan|continued|cont\.|sambungan)\b", nxt_cap, re.IGNORECASE))
            if is_cont_cap:
                return False

            # Guard 1: Distinct numbered normalized_id (e.g. '4.8' vs '4.9')
            curr_nid = str(curr_t.get("normalized_id") or "").strip()
            nxt_nid = str(nxt_t.get("normalized_id") or "").strip()
            if nxt_nid and not nxt_nid.upper().startswith("OCR") and nxt_nid != curr_nid:
                return True

            # Guard 2: Explicit new table caption on nxt (e.g. 'Tabel IV.9 ...')
            if nxt_cap and re.match(r"^(?:tabel|table)\s+(?:[IVX]+|\d+)", nxt_cap, re.IGNORECASE):
                curr_cap = str(curr_t.get("caption") or "").strip()
                if not curr_cap or nxt_cap.lower() != curr_cap.lower():
                    return True

            # Guard 3: curr already ended with a closing Total/Jumlah row
            if _row_has_terminal_total(curr_t.get("rows", [])):
                return True

            # Guard 4: Spatial page-boundary check when page heights are known
            curr_h = float(curr_t.get("page_height_pt") or 0.0)
            nxt_h = float(nxt_t.get("page_height_pt") or 0.0)
            curr_box = curr_t.get("bbox") or []
            nxt_box = nxt_t.get("bbox") or []
            if curr_h > 0.0 and len(curr_box) >= 4:
                # A split table must reach near the bottom of page N (no large narrative block below it)
                if float(curr_box[3]) < curr_h * 0.65:
                    return True
            if nxt_h > 0.0 and len(nxt_box) >= 4:
                # Continuation on page N+1 must start near the top margin (not mid-page below new items)
                if float(nxt_box[1]) > nxt_h * 0.35:
                    return True

            return False

        stitched: List[Dict[str, Any]] = []
        skip_indices = set()

        for i in range(len(tables)):
            if i in skip_indices:
                continue
            curr = tables[i]
            if i + 1 < len(tables):
                nxt = tables[i + 1]
                if nxt.get("page") == curr.get("page", 0) + 1 and nxt.get("num_cols") == curr.get("num_cols"):
                    if not _is_distinct_next_table(curr, nxt):
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
                                                    "bbox": None,
                                                    "cell_rect": None,
                                                    "bbox_approx": True
                                                }
                                    merged_rows.append(r)

                                merged_table = dict(curr)
                                merged_table["rows"] = merged_rows
                                merged_table["num_rows"] = len(merged_rows)
                                merged_table["is_cross_page"] = True
                                merged_table["stitched_pages"] = [curr.get("page", 1), nxt.get("page", 1)]
                                merged_table["absorbed_table_ids"] = list(curr.get("absorbed_table_ids", [])) + [nxt.get("table_id")]
                                stitched.append(merged_table)
                                skip_indices.add(i + 1)
                                continue

            stitched.append(curr)

        return stitched
