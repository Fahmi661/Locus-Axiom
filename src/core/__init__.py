from src.core.quad_tuple_verifier import (
    ClaimQuadTuple,
    QuadVerificationResult,
    extract_quad_tuples_from_sentence,
    verify_quad_tuple_against_table,
    parse_academic_number,
    check_rounding_and_truncation,
    match_variable_row_score,
    classify_column_header
)
from src.core.spss_likert_engine import (
    CleanedSPSSRow,
    LikertClauseClaim,
    parse_spss_frequency_table,
    is_spss_frequency_table,
    extract_likert_claims_by_clause,
    route_claim_to_exact_table,
    normalize_table_id,
    check_likert_row_sum_in_sentence,
    LIKERT_HUMAN_LABEL,
    LIKERT_ROW_ALIASES
)
