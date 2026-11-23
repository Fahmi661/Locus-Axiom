from src.core.quad_tuple_verifier import (
    ExtractedNumberToken,
    ClaimQuadTuple,
    QuadVerificationResult,
    parse_academic_number,
    normalize_variable_stem,
    normalize_text_dashes,
    match_variable_row_score,
    classify_column_header,
    extract_quad_tuples_from_sentence,
    check_rounding_and_truncation,
    verify_quad_tuple_against_table,
    STAT_TYPES,
    TEXT_STAT_PATTERNS,
    COLUMN_HEADER_SYNONYMS,
    VARIABLE_ALIAS_MAP
)
