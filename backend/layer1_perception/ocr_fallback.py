"""
LOCUS OCR Table Fallback Module.
Layer 1 Perception - Handles screenshot / scanned tables (SPSS, Excel, Word).
Integrates RapidOCR + RapidTable (Apache-2.0) with robust OpenCV contour reconstruction.
"""

from typing import List, Dict, Any, Optional, Tuple
import os
import cv2
import numpy as np
from PIL import Image

# Try loading RapidOCR and RapidTable (Apache-2.0)
try:
    from rapidocr_onnxruntime import RapidOCR
    HAS_RAPID_OCR = True
except ImportError:
    HAS_RAPID_OCR = False

try:
    from rapid_table import RapidTable
    HAS_RAPID_TABLE = True
except ImportError:
    HAS_RAPID_TABLE = False


class OcrTableFallback:
    _ocr_engine = None
    _table_engine = None

    @staticmethod
    def correct_numeric_ocr(text: str) -> str:
        """
        Numeric-Aware OCR Post-Corrector (v3.1):
        Corrects typical typographical OCR confusions in numerical columns:
        'O'/'o' -> '0', 'l'/'I'/'|' -> '1', 'S' -> '5' when flanked by numbers or decimals.
        """
        import re
        s = text.strip()
        # Replace O/o with 0
        s = re.sub(r"\b[Oo](?=\.|\d)", "0", s)
        s = re.sub(r"(?<=\d|\.)[Oo]", "0", s)
        # Replace l/I/| with 1
        s = re.sub(r"\b[lI\|](?=\.|\d)", "1", s)
        s = re.sub(r"(?<=\d|\.)[lI\|]", "1", s)
        # Replace S with 5
        s = re.sub(r"\bS(?=\.|\d)", "5", s)
        s = re.sub(r"(?<=\d|\.)S", "5", s)
        return s

    @staticmethod
    def deskew_image_cv(image_cv: np.ndarray) -> np.ndarray:
        """
        Automatic OpenCV Deskewing for scanned documents:
        Estimates skew angle from text contours and rotates image to horizontal.
        """
        try:
            if len(image_cv.shape) == 3:
                gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
            else:
                gray = image_cv

            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            coords = np.column_stack(np.where(thresh > 0))
            if len(coords) < 100:
                return image_cv

            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            elif angle > 45:
                angle = 90 - angle
            else:
                angle = -angle

            if abs(angle) > 0.4 and abs(angle) < 20.0:
                (h, w) = image_cv.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(image_cv, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                return rotated
            return image_cv
        except Exception:
            return image_cv

    @classmethod
    def get_engines(cls):
        if HAS_RAPID_OCR and cls._ocr_engine is None:
            try:
                cls._ocr_engine = RapidOCR()
            except Exception:
                cls._ocr_engine = None

        if HAS_RAPID_TABLE and cls._table_engine is None:
            try:
                cls._table_engine = RapidTable()
            except Exception:
                cls._table_engine = None

        return cls._ocr_engine, cls._table_engine

    @staticmethod
    def normalize_cells(rows: List[Any]) -> List[List[Dict[str, Any]]]:
        """
        Normalizes any list of rows into a uniform List[List[Dict]] where each cell has:
        {"row": r_idx + 1, "col": c_idx + 1, "row_idx": r_idx, "col_idx": c_idx, "text": text, "raw_val": text, "bbox": bbox}
        """
        if not rows:
            return []
        normalized_rows: List[List[Dict[str, Any]]] = []
        for r_idx, row in enumerate(rows):
            if not isinstance(row, (list, tuple)):
                row = [row]
            s_row = []
            for c_idx, cell in enumerate(row):
                c_text = ""
                c_bbox = [0, 0, 0, 0]
                if isinstance(cell, str):
                    c_text = cell
                elif isinstance(cell, dict):
                    c_text = cell.get("text") or cell.get("raw_val") or ""
                    c_bbox = cell.get("bbox", [0, 0, 0, 0])
                else:
                    c_text = str(cell)

                s_row.append({
                    "row": cell.get("row", r_idx + 1) if isinstance(cell, dict) else (r_idx + 1),
                    "col": cell.get("col", c_idx + 1) if isinstance(cell, dict) else (c_idx + 1),
                    "row_idx": cell.get("row_idx", r_idx) if isinstance(cell, dict) else r_idx,
                    "col_idx": cell.get("col_idx", c_idx) if isinstance(cell, dict) else c_idx,
                    "text": c_text,
                    "raw_val": c_text,
                    "bbox": c_bbox
                })
            normalized_rows.append(s_row)
        return normalized_rows

    @classmethod
    def extract_table_from_image(cls, image_path_or_array) -> Dict[str, Any]:
        """
        Extracts structured table cells from a screenshot image (SPSS / Excel).
        Uses RapidTable + RapidOCR if available, or OpenCV contour grid reconstruction.
        """
        if isinstance(image_path_or_array, str):
            image_cv = cv2.imread(image_path_or_array)
        else:
            image_cv = image_path_or_array

        if image_cv is None:
            return {"num_rows": 0, "num_cols": 0, "cells": [], "rows": []}

        image_cv = cls.deskew_image_cv(image_cv)

        ocr, table_model = cls.get_engines()

        # Path A: Using RapidTable + RapidOCR if installed
        if ocr is not None and table_model is not None:
            try:
                ocr_results, _ = ocr(image_cv)
                table_html, cell_boxes, _ = table_model(image_cv, ocr_results)
                res = {
                    "source": "RAPID_TABLE_ONNX",
                    "html": table_html,
                    "cells": cell_boxes,
                    "rows": cls.reconstruct_table_grid_cv(image_cv).get("rows", [])
                }
                res["rows"] = cls.normalize_cells(res["rows"])
                return res
            except Exception:
                pass

        # Path B: OpenCV Morphological Grid Reconstruction
        res = cls.reconstruct_table_grid_cv(image_cv)
        res["rows"] = cls.normalize_cells(res.get("rows", []))
        return res

    @classmethod
    def reconstruct_table_grid_cv(cls, image_cv: np.ndarray) -> Dict[str, Any]:
        """
        Reconstructs table grid cells, rows, and columns using OpenCV morphological kernels.
        """
        if len(image_cv.shape) == 3:
            gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_cv

        # Adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
        )

        # Detect horizontal and vertical grid lines
        scale = 20
        horiz_size = int(gray.shape[1] / scale)
        vert_size = int(gray.shape[0] / scale)

        horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(1, horiz_size), 1))
        vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(1, vert_size)))

        horiz_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horiz_kernel)
        vert_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vert_kernel)

        table_mask = cv2.add(horiz_lines, vert_lines)
        contours, _ = cv2.findContours(table_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        cells = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 25 < w < gray.shape[1] * 0.95 and 12 < h < gray.shape[0] * 0.8:
                cells.append({
                    "bbox": [x, y, x + w, y + h],
                    "width": w,
                    "height": h,
                    "y_center": y + (h / 2),
                    "x_center": x + (w / 2)
                })

        # Sort cells into rows and columns
        cells.sort(key=lambda c: (c["bbox"][1], c["bbox"][0]))
        rows: List[List[Dict[str, Any]]] = []
        curr_row: List[Dict[str, Any]] = []
        curr_y = None

        for c in cells:
            if curr_y is None or abs(c["bbox"][1] - curr_y) <= 8.0:
                curr_row.append(c)
                curr_y = c["bbox"][1]
            else:
                curr_row.sort(key=lambda x: x["bbox"][0])
                rows.append(curr_row)
                curr_row = [c]
                curr_y = c["bbox"][1]

        if curr_row:
            curr_row.sort(key=lambda x: x["bbox"][0])
            rows.append(curr_row)

        num_rows = len(rows)
        num_cols = max([len(r) for r in rows]) if rows else 0

        return {
            "source": "OPENCV_CONTOUR_RECONSTRUCTION",
            "num_rows": num_rows,
            "num_cols": num_cols,
            "total_cells": len(cells),
            "rows": rows
        }
