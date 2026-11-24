"""
LOCUS v3.5 Semantic Numeric Type-Safety & Non-Data Filter Guard.
Distinguishes between empirical table-linked statistical metrics and non-statistical numerals:
- Citation years: (2021), (Ghozali, 2021), (Sugiyono, 2019:45)
- Year ranges: 2018-2021, 2019-2023, 2020 s/d 2022
- Legal/indices: UU No. 4, Bab 4, Tabel IV.2, Hal. 12, item 1, butir ke-3, H1
- Scale & rule thresholds: skala 1 sampai 5, VIF < 10, tolerance > 0.10, alpha 0.05
- Non-stat durations: selama 3 tahun, 4 periode, triwulan 2
Only genuine empirical tokens (STAT_METRIC) are permitted into the ClaimQuadTuple engine.
"""

import re
from typing import Optional


# Regex patterns for sentence-level non-data detection
THEORY_CITATION_ONLY_REGEX = re.compile(
    r"^(?:menurut|berdasarkan\s+(?:teori|penelitian|pendapat)|dalam\s+penelitian)\s+[A-Za-z\s]+(?:\(\s*\d{4}\s*\)|,\s*\d{4})",
    re.IGNORECASE
)

DECISION_CRITERIA_REGEX = re.compile(
    r"(?:"
    r"kriteria\s+(?:pengujian|pengambilan\s+keputusan|evaluasi|uji)|"
    r"(?:jika|apabila)\s+(?:nilai\s+)?(?:sig\.?|signifikansi|p-?value|t-?hitung|f-?hitung|tolerance|vif)\s*[<>=]|"
    r"hipotesis\s+(?:diterima|ditolak)\s+(?:jika|apabila)|"
    r"dikatakan\s+(?:valid|reliabel|normal|homogen|bebas\s+multikolinearitas)\s+(?:jika|apabila)|"
    r"pedoman\s+interpretasi|"
    r"skala\s+(?:pengukuran|likert)\s+(?:yang\s+digunakan\s+adalah\s+)?(?:skala\s+)?\d+\s+(?:sampai|hingga|s/d|-)\s*\d+"
    r")",
    re.IGNORECASE
)

TABLE_EMPIRICAL_ANCHOR_REGEX = re.compile(
    r"\b(?:tabel|table|hasil\s+uji|menunjukkan\s+nilai|diperoleh\s+nilai|sebesar|senilai)\b",
    re.IGNORECASE
)


def is_non_data_sentence(sentence: str) -> bool:
    """
    Returns True if the sentence is purely theoretical, methodological (e.g. sample year coverage),
    or a textbook rule/criterion definition without any empirical table findings.
    """
    if not sentence or not sentence.strip():
        return True

    s_clean = sentence.strip()
    s_lower = s_clean.lower()

    # If it explicitly references a table or empirical test result, it is not non-data
    if re.search(r"\btabel\s+(?:[ivx]+|\d+)", s_lower) or re.search(r"\bhasil\s+(?:analisis|uji|regresi|deskriptif)\b", s_lower):
        # But verify it is not just a sentence defining test criteria with table mention
        if not re.search(r"kriteria\s+pengujian|jika\s+nilai\s+sig", s_lower):
            return False

    # Check textbook rule or decision criteria definition
    if DECISION_CRITERIA_REGEX.search(s_clean):
        # If it doesn't state empirical results, it's non-data
        if not re.search(r"\b(?:diperoleh|tercatat|sebesar\s+\d|senilai\s+\d)\b", s_lower):
            return True

    # Check pure theory/citation sentence
    if THEORY_CITATION_ONLY_REGEX.search(s_clean):
        if not re.search(r"\b(?:sebesar\s+\d|senilai\s+\d|tabel\s+\d|tabel\s+[ivx]+)\b", s_lower):
            return True

    # Check methodology-only sample timeframe sentence: e.g.
    # "Penelitian ini menggunakan data tahun 2019 sampai 2021 menurut Ghozali (2021) dengan skala 1 sampai 5."
    has_year_coverage = bool(re.search(r"(?:periode|tahun|data)\s+(?:dari\s+tahun\s+)?\d{4}\s+(?:sampai|hingga|s/d|-)\s*\d{4}", s_lower))
    has_method_keywords = bool(re.search(r"\b(?:penelitian\s+ini\s+menggunakan|populasi|sampel\s+yang\s+digunakan|skala\s+pengukuran|kuesioner)\b", s_lower))
    has_stat_keywords = bool(re.search(r"\b(?:mean|rata-rata|rerata|standar\s+deviasi|minimum|terendah|maksimum|tertinggi)\b", s_lower))

    if has_year_coverage and has_method_keywords and not has_stat_keywords:
        return True

    return False


def classify_numeric_span(sentence: str, start: int, end: int, raw_token: str) -> str:
    """
    Classifies a specific numeric token span in a sentence into one of:
    - 'CITATION_YEAR'
    - 'YEAR_RANGE'
    - 'LEGAL_OR_INDEX'
    - 'SCALE_OR_RULE_THRESHOLD'
    - 'DURATION_NON_STAT'
    - 'STAT_METRIC' (Only this category can be bound to ClaimQuadTuple)
    """
    token = raw_token.strip()
    s_len = len(sentence)
    token_val = token.replace(",", ".").rstrip("%")

    # Clean surrounding context windows
    left_ctx_50 = sentence[max(0, start - 50):start].lower()
    left_ctx_25 = sentence[max(0, start - 25):start].lower()
    left_ctx_15 = sentence[max(0, start - 15):start].lower()
    right_ctx_35 = sentence[end:min(s_len, end + 35)].lower()
    right_ctx_15 = sentence[end:min(s_len, end + 15)].lower()

    # Check integer value if applicable
    int_val: Optional[int] = None
    try:
        int_val = int(token_val)
    except ValueError:
        try:
            f_val = float(token_val)
            if f_val.is_integer():
                int_val = int(f_val)
        except ValueError:
            pass

    # 1. YEAR & CITATION DETECTION
    if int_val is not None and 1950 <= int_val <= 2035:
        # Check if inside parentheses (e.g. '(2021)', '(Ghozali, 2021)', '(Sugiyono, 2019:45)')
        # Look backwards for '(' and forwards for ')' without crossing sentence boundaries
        open_paren_idx = sentence.rfind("(", max(0, start - 30), start)
        close_paren_idx = sentence.find(")", end, min(s_len, end + 30))
        if open_paren_idx != -1 and close_paren_idx != -1:
            paren_content = sentence[open_paren_idx:close_paren_idx + 1]
            if re.search(r"\(\s*(?:[A-Za-z\s]+,?\s*)?\d{4}(?::\d+)?\s*\)", paren_content):
                return "CITATION_YEAR"

        # Check year prefix keywords: 'tahun 2021', 'periode 2019', 'sejak 2020', 'edisi 2018', 'UU No. 2003', 'pada 2021'
        if re.search(r"\b(?:tahun|thn|periode|sejak|edisi|uu\s+no\.?|pp\s+no\.?|psak)\s*$", left_ctx_15):
            return "CITATION_YEAR"
        if re.search(r"\b(?:di|pada|hingga|sampai|mulai|awal|akhir)\s*$", left_ctx_15):
            return "CITATION_YEAR"
        if re.search(r"\b(?:pada\s+tahun|sampai\s+tahun|hingga\s+tahun|selama\s+tahun)\s*$", left_ctx_25):
            return "CITATION_YEAR"

        # Check year range context: '2019 sampai 2021', '2018 - 2020', '2019 s/d 2022'
        if re.search(r"^\s*(?:sampai|hingga|s/d|-|–)\s*(?:tahun\s+)?\d{4}", right_ctx_25 if 'right_ctx_25' in locals() else right_ctx_35):
            return "YEAR_RANGE"
        if re.search(r"\b\d{4}\s*(?:sampai|hingga|s/d|-|–)\s*$", left_ctx_25):
            return "YEAR_RANGE"
        if re.search(r"\b(?:periode|tahun)\s+\d{4}\s+(?:sampai|hingga|s/d|-|–)\s*$", left_ctx_50):
            return "YEAR_RANGE"

    # 2. LEGAL & DOCUMENT INDEX NUMBERS
    # 'item 1', 'butir ke-3', 'pertanyaan 5', 'indikator 2', 'hipotesis 1', 'H1', 'Tabel IV.2', 'Bab 4', 'Gambar 4.1'
    if re.search(r"\b(?:item|butir(?:\s+ke-?)?|pertanyaan|indikator|pernyataan|hipotesis|variabel|tabel|table|bab|gambar|hal\.?|halaman|lampiran|persamaan|model|kuesioner|sampel\s+ke-?|responden\s+ke-?)\s*$", left_ctx_25):
        return "LEGAL_OR_INDEX"
    if re.search(r"\b(?:pasal|ayat|uu\s+no\.?|peraturan(?:\s+pemerintah)?)\s*$", left_ctx_25):
        return "LEGAL_OR_INDEX"
    if re.match(r"^[hH]\d+$", token):
        return "LEGAL_OR_INDEX"

    # 3. SCALE & RULE THRESHOLDS
    # Skala Likert: 'skala 1 sampai 5', 'skor 1-5', 'skala likert 1-5'
    if re.search(r"\bskala(?:\s+likert|\s+pengukuran)?\s*$", left_ctx_25) or re.search(r"\bskala\s+\d+\s+(?:sampai|hingga|s/d|-)\s*$", left_ctx_25):
        return "SCALE_OR_RULE_THRESHOLD"
    if re.search(r"^\s*(?:sampai|hingga|s/d|-)\s*\d+\s*(?:pada\s+skala|skala)", right_ctx_35):
        return "SCALE_OR_RULE_THRESHOLD"
    if re.search(r"\bskor\s*$", left_ctx_15) and re.search(r"^\s*(?:sampai|hingga|s/d|-)\s*\d+", right_ctx_15):
        return "SCALE_OR_RULE_THRESHOLD"

    # Rule thresholds: VIF < 10, tolerance > 0.10, alpha 0.05 / 5%, Cronbach's alpha > 0.60/0.70
    if re.search(r"\bvif\s*(?:<|>|<=|>=|=|adalah|sebesar|kurang\s+dari|lebih\s+dari)?\s*$", left_ctx_25):
        return "SCALE_OR_RULE_THRESHOLD"
    if re.search(r"\btolerance\s*(?:<|>|<=|>=|=|adalah|sebesar|kurang\s+dari|lebih\s+dari)?\s*$", left_ctx_25):
        return "SCALE_OR_RULE_THRESHOLD"
    if re.search(r"\b(?:alpha|taraf\s+signifikansi|tingkat\s+signifikansi|significance\s+level)\s*(?:sebesar|=)?\s*$", left_ctx_25):
        # e.g. 'taraf signifikansi 5%', 'alpha 0,05'
        return "SCALE_OR_RULE_THRESHOLD"
    if re.search(r"\bcronbach(?:'s)?\s+alpha\s*(?:>|<|>=|<=|=|sebesar)?\s*$", left_ctx_25):
        return "SCALE_OR_RULE_THRESHOLD"
    if re.search(r"\b(?:r\s+tabel|t\s+tabel|f\s+tabel|z\s+tabel)\s*(?:sebesar|=)?\s*$", left_ctx_25):
        return "SCALE_OR_RULE_THRESHOLD"
    if re.search(r"\b(?:durbin[\s-]watson|dw)\s+(?:antara|tabel)\s*$", left_ctx_25):
        return "SCALE_OR_RULE_THRESHOLD"
    if re.search(r"(?:lebih\s+besar\s+dari|lebih\s+kecil\s+dari|kurang\s+dari|lebih\s+dari|di\s+atas|di\s+bawah|[<>≤≥])\s*$", left_ctx_25):
        if token_val in ("0.05", "0.01", "0.10"):
            return "SCALE_OR_RULE_THRESHOLD"
        try:
            if round(float(token_val), 4) in (0.05, 0.01, 0.10):
                return "SCALE_OR_RULE_THRESHOLD"
        except ValueError:
            pass

    # 4. NON-STATISTICAL DURATION / PERIOD
    # 'selama 3 tahun', '4 periode', 'triwulan 2', 'kuartal 3'
    # EXCEPT if sentence discusses audit delay / delay / hari where duration IS the statistical variable
    s_lower = sentence.lower()
    is_delay_context = bool(re.search(r"\b(?:delay|keterlambatan|hari|waktu\s+tunggu)\b", s_lower))
    if not is_delay_context:
        if re.search(r"\b(?:selama|dalam|kurun\s+waktu)\s*$", left_ctx_15) and re.search(r"^\s*(?:tahun|thn|bulan|periode|hari|minggu)", right_ctx_15):
            return "DURATION_NON_STAT"
        if re.search(r"^\s*(?:tahun|thn|periode|triwulan|kuartal|semester|siklus)\b", right_ctx_15):
            return "DURATION_NON_STAT"
        if re.search(r"\b(?:triwulan|kuartal|semester)\s*$", left_ctx_15):
            return "DURATION_NON_STAT"

    # 5. Passed all guards -> genuine statistical metric token
    return "STAT_METRIC"
