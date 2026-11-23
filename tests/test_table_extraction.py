"""
Unit Tests for LOCUS Table Extraction and Number Normalization.
Ensures accurate cell parsing, 3-line table extraction, and dual-locale detection.
"""

import os
import pytest
from backend.layer1_perception.number_normalizer import NumberNormalizer
from backend.layer1_perception.pdf_reader import FastPdfReader


def test_dual_locale_column_detection():
    # Indonesian PUEBI column
    id_col = ["12,45", "0,018", "1.250,00", "45,80"]
    assert NumberNormalizer.detect_column_locale(id_col) == "ID_PUEBI"

    # SPSS US column
    spss_col = [".000", ".018", "12.45", "1,250.00"]
    assert NumberNormalizer.detect_column_locale(spss_col) == "SPSS_US"


def test_parse_numeric_tokens():
    # SPSS leading dot
    p1 = NumberNormalizer.parse_numeric(".000", "SPSS_US")
    assert p1 is not None
    assert p1["float_val"] == 0.0
    assert p1["decimals"] == 3

    # Indonesian comma
    p2 = NumberNormalizer.parse_numeric("12,45", "ID_PUEBI")
    assert p2 is not None
    assert p2["float_val"] == 12.45
    assert p2["decimals"] == 2

    # Number with significance asterisk
    p3 = NumberNormalizer.parse_numeric("0,018**", "ID_PUEBI")
    assert p3 is not None
    assert p3["float_val"] == 0.018


def test_preset_pdf_extraction():
    preset_1_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "presets", "preset_1_ml_polarity.pdf"
    )
    assert os.path.exists(preset_1_path)

    doc_graph = FastPdfReader.process_pdf(preset_1_path)
    assert doc_graph["num_pages"] >= 1
    assert len(doc_graph["tables"]) >= 1
    table = doc_graph["tables"][0]
    assert table["num_cols"] == 4
    assert len(table["rows"]) == 3
