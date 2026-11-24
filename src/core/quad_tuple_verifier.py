"""
LOCUS v3.2 - Quad-Tuple Grounding & Rounding Tolerance Engine
Lisensi: MIT / Apache-2.0 (100% Permissive, Offline CPU-Ready)

Mencocokkan secara ketat 4 komponen:
1. Nama Variabel (Row Grounding + Morphological Alias Resolution)
2. Jenis Statistik (Column Grounding: Mean, N, Minimum, Maximum, Std. Deviation, Sig, t/F, %)
3. Nilai Numerik (Indonesian/English Locale Normalization + Scale Alignment)
4. Toleransi Pembulatan (Symmetric Half-Unit Interval + SPSS Truncation Detection)
"""

from __future__ import annotations
import math
import os
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from src.core.semantic_numeric_guard import classify_numeric_span, is_non_data_sentence


# =====================================================================
# 1. DEFINISI TIPE STATISTIK KANONIK & KAMUS SINONIM DUA ARAH
# =====================================================================

STAT_TYPES = (
    "N",
    "MINIMUM",
    "MAXIMUM",
    "MEAN",
    "STD_DEV",
    "P_VALUE",
    "STAT_TEST",
    "PERCENTAGE",
)

# Pola pendeteksi Jenis Statistik di dalam kalimat paragraf Bab IV (diurutkan dari paling spesifik)
TEXT_STAT_PATTERNS: Dict[str, List[str]] = {
    "STD_DEV": [
        r"standar\s+deviasi(?:\s+sebesar|\s+adalah|\s+senilai|\s*=)?",
        r"simpangan\s+baku(?:\s+sebesar|\s+adalah|\s+senilai|\s*=)?",
        r"std\.?\s*deviation",
        r"std\.?\s*dev\.?",
        r"\bsd\b(?:\s+sebesar|\s*=)",
    ],
    "MINIMUM": [
        r"nilai\s+terendah(?:nya)?(?:\s+sebesar|\s+adalah|\s+senilai|\s*=)?",
        r"nilai\s+minimum(?:nya)?(?:\s+sebesar|\s+adalah|\s+senilai|\s*=)?",
        r"nilai\s+paling\s+rendah",
        r"nilai\s+terkecil",
        r"skor\s+terendah",
        r"skor\s+minimum",
        r"\bterendah(?:nya)?\b",
        r"\bterkecil(?:nya)?\b",
        r"paling\s+rendah",
        r"paling\s+kecil",
        r"\bminimum(?:\s+sebesar|\s+adalah|\s*=)?",
        r"\bmin\.?(?:\s+sebesar|\s*=)",
    ],
    "MAXIMUM": [
        r"nilai\s+tertinggi(?:nya)?(?:\s+sebesar|\s+adalah|\s+senilai|\s*=)?",
        r"nilai\s+maksimum(?:nya)?(?:\s+sebesar|\s+adalah|\s+senilai|\s*=)?",
        r"nilai\s+maksimal(?:nya)?",
        r"nilai\s+paling\s+tinggi",
        r"nilai\s+terbesar",
        r"skor\s+tertinggi",
        r"skor\s+maksimum",
        r"\btertinggi(?:nya)?\b",
        r"\bterbesar(?:nya)?\b",
        r"paling\s+tinggi",
        r"paling\s+besar",
        r"tingkat\s+tertinggi",
        r"\bmaksimum(?:\s+sebesar|\s+adalah|\s*=)?",
        r"\bmaximum(?:\s+sebesar|\s+adalah|\s*=)?",
        r"\bmax\.?(?:\s+sebesar|\s*=)",
    ],
    "MEAN": [
        r"nilai\s+rata[\s\u2010-\u2015\u2212\-]+rata(?:nya)?(?:\s*\(\s*mean\s*\))?(?:\s+sebesar|\s+adalah|\s+senilai|\s*=)?",
        r"rata[\s\u2010-\u2015\u2212\-]+rata(?:\s+hitung)?(?:\s+sebesar|\s+adalah|\s+senilai|\s*=)?",
        r"rerata(?:\s+sebesar|\s+adalah|\s+senilai|\s*=)?",
        r"\bmean(?:\s+sebesar|\s+adalah|\s+senilai|\s*=)?",
        r"skor\s+rata[\s\u2010-\u2015\u2212\-]+rata",
    ],
    "N": [
        r"jumlah\s+sampel(?:\s+sebanyak|\s+sebesar|\s+adalah|\s*=)?",
        r"jumlah\s+observasi(?:\s+sebanyak|\s+sebesar|\s+adalah|\s*=)?",
        r"jumlah\s+responden(?:\s+sebanyak|\s+sebesar|\s+adalah|\s*=)?",
        r"jumlah\s+data(?:\s+sebanyak|\s+sebesar|\s+adalah|\s*=)?",
        r"sebanyak\s+\d+\s+(?:perusahaan|responden|siswa|sampel|observasi|data)",
        r"\bn\s*=\s*",
        r"valid\s+n",
    ],
    "P_VALUE": [
        r"nilai\s+signifikansi(?:\s+sebesar|\s+adalah|\s*=)?",
        r"tingkat\s+signifikansi(?:\s+sebesar|\s+adalah|\s*=)?",
        r"asymp\.?\s*sig\.?(?:\s*\(2-tailed\))?",
        r"\bsig\.?(?:\s*\(2-tailed\))?(?:\s+sebesar|\s+adalah|\s*=)?",
        r"\bp\s*-?\s*value(?:\s+sebesar|\s+adalah|\s*=)?",
        r"\bprob(?:abilitas|\.)?(?:\s+sebesar|\s+adalah|\s*=)?",
        r"\bp\s*[=<]\s*",
    ],
    "STAT_TEST": [
        r"\bt\s*-?\s*hitung(?:\s+sebesar|\s+adalah|\s*=)?",
        r"\bt\s+hitung(?:\s+sebesar|\s+adalah|\s*=)?",
        r"nilai\s+t(?:\s+sebesar|\s+adalah|\s*=)",
        r"\bf\s*-?\s*hitung(?:\s+sebesar|\s+adalah|\s*=)?",
        r"\bf\s+hitung(?:\s+sebesar|\s+adalah|\s*=)?",
        r"test\s+statistic",
    ],
    "PERCENTAGE": [
        r"persentase(?:\s+sebesar|\s+adalah|\s+mencapai)?",
        r"proporsi(?:\s+sebesar|\s+adalah)?",
    ],
}

# Pola pencocokan Header Kolom pada Tabel PDF (SPSS / EViews / Tabel Manual)
COLUMN_HEADER_SYNONYMS: Dict[str, List[str]] = {
    "N": ["n", "valid n", "valid n (listwise)", "jumlah", "sampel", "observasi", "frekuensi", "f"],
    "MINIMUM": ["minimum", "min", "min.", "nilai terendah", "terendah", "nilai minimum", "skor terendah"],
    "MAXIMUM": ["maximum", "max", "max.", "maksimum", "nilai tertinggi", "tertinggi", "nilai maksimum", "skor tertinggi"],
    "MEAN": ["mean", "rata-rata", "rata - rata", "rerata", "average", "skor rata-rata", "mean score"],
    "STD_DEV": ["std. deviation", "std deviation", "std. dev.", "std. dev", "sd", "standar deviasi", "simpangan baku"],
    "P_VALUE": ["sig.", "sig", "sig. (2-tailed)", "asymp. sig. (2-tailed)", "p-value", "p value", "prob.", "prob", "signifikansi"],
    "STAT_TEST": ["t", "f", "z", "t-hitung", "f-hitung", "t-statistic", "f-statistic", "test statistic", "hitung"],
    "PERCENTAGE": ["%", "persentase", "percent", "valid percent", "cumulative percent", "proporsi"],
}

# Kamus Sinonim & Singkatan Variabel Skripsi Indonesia
VARIABLE_ALIAS_MAP: Dict[str, List[str]] = {
    "ukkap": ["ukuran kap", "ukuran kantor akuntan publik", "sqrtkap", "kap", "ukap"],
    "auddelay": ["audit delay", "keterlambatan audit", "audit report lag"],
    "roa": ["return on asset", "return on assets", "profitabilitas"],
    "roe": ["return on equity", "profitabilitas"],
    "dar": ["debt to asset ratio", "leverage", "solvabilitas"],
    "der": ["debt to equity ratio", "leverage", "struktur modal"],
    "size": ["ukuran perusahaan", "firm size", "ln size", "lnsize"],
    "ngain": ["gain score", "n-gain", "nilai gain", "peningkatan hasil belajar"],
    "pnglm": ["pengalaman auditor", "sqrtpnglm", "pengalaman"],
    "spes": ["spesialisasi auditor", "spesialisasi", "sqrtspes"],
}


# =====================================================================
# 2. STRUKTUR DATA QUAD-TUPLE & HASIL VERIFIKASI
# =====================================================================

@dataclass
class ExtractedNumberToken:
    raw_text: str
    value: float
    decimals: int
    is_percentage: bool
    char_start: int
    char_end: int


@dataclass
class ClaimQuadTuple:
    """Representasi 4 komponen wajib pada setiap klaim numerik."""
    sentence_text: str
    variable_name: str               # 1. Nama Variabel
    stat_type: str                   # 2. Jenis Statistik (Mean, N, Minimum, Maximum, Std. Deviation, dll.)
    numeric_value: float             # 3. Nilai Numerik
    decimal_places: int              # 4. Presisi Desimal untuk Toleransi Pembulatan
    raw_number_str: str
    is_percentage: bool = False
    operator: str = "EQ"             # "EQ", "GT", "GTE", "LT", "LTE"
    extraction_confidence: float = 1.0


@dataclass
class QuadVerificationResult:
    status: str                      # VALID_EXACT, VALID_ROUNDED, TRUNCATION_WARNING, VALUE_MISMATCH, COLUMN_SWAP_ERROR, UNLINKED_SKIP
    quad: ClaimQuadTuple
    matched_row_label: Optional[str] = None
    matched_col_label: Optional[str] = None
    row_confidence: float = 0.0
    col_confidence: float = 0.0
    table_cell_raw: Optional[str] = None
    table_cell_value: Optional[float] = None
    allowed_lower_bound: Optional[float] = None
    allowed_upper_bound: Optional[float] = None
    swapped_column_found: Optional[str] = None
    explanation_id: str = ""


# =====================================================================
# 3. NORMALISASI ANGKA, VARIABEL, DAN HEADER KOLOM
# =====================================================================

def parse_academic_number(raw: str) -> Optional[Tuple[float, int, bool]]:
    """
    Mengubah string angka format Indonesia/Inggris/SPSS menjadi (float, jumlah_desimal, is_percentage).
    Mendukung format: '84,32', '1.250,50', '.425', '-2,145', '78,57%'.
    """
    s = raw.strip()
    if not s:
        return None
    is_pct = s.endswith("%")
    if is_pct:
        s = s[:-1].strip()

    s = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d]", "-", s)
    # Tangani format SPSS tanpa nol di depan titik atau koma, misal '.425', ',17', '-.425', '-,45', ',00'
    s = re.sub(r"^([+-]?)\s*[,.](\d+)$", r"\g<1>0.\g<2>", s)
    if s.startswith("."):
        s = "0" + s
    elif s.startswith(","):
        s = "0." + s[1:]
    elif s.startswith("-."):
        s = "-0." + s[2:]
    elif s.startswith("-,"):
        s = "-0." + s[2:]
    elif s.startswith("+."):
        s = "0." + s[2:]
    elif s.startswith("+,"):
        s = "0." + s[2:]

    # Pisahkan format ribuan dan desimal Indonesia vs Inggris
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # Format Indonesia: 1.250,45
            s_clean = s.replace(".", "").replace(",", ".")
        else:
            # Format Inggris: 1,250.45
            s_clean = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2:
            s_clean = parts[0] + "." + parts[1]
        else:
            s_clean = s.replace(",", "")
    else:
        s_clean = s

    try:
        val = float(s_clean)
    except ValueError:
        return None

    if "." in s_clean:
        dec_part = s_clean.split(".")[1]
        decimals = len(dec_part)
    else:
        decimals = 0

    return val, decimals, is_pct


def normalize_variable_stem(name: str) -> str:
    """Mengupas prefiks kode variabel regresi (X1_, X2_, Y_, Z_), transformasi SPSS (SQRT, LN, LOG) dan kata umum."""
    s = name.lower().strip()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(
        r"^(?:[xyz]\d*[_\-\s\.]+|variabel\s+|variable\s+|sqrt[_\s]*|ln[_\s]*|log10[_\s]*|log[_\s]*|abs[_\s]*|zscore[_\s]*)+",
        "",
        s,
    )
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def match_variable_row_score(claim_var: str, row_header: str) -> float:
    """
    Menghitung skor kecocokan antara Nama Variabel di klaim dengan Nama Baris di tabel.
    Menggabungkan Exact Stem, Alias Kamus, Subsequence Acronym, dan Character Similarity.
    """
    c_raw = claim_var.lower().strip()
    r_raw = row_header.lower().strip()
    if not c_raw or not r_raw:
        return 0.0

    c_stem = normalize_variable_stem(c_raw)
    r_stem = normalize_variable_stem(r_raw)

    if c_stem == r_stem or c_raw == r_raw:
        return 1.0

    # Cek kamus alias/singkatan variabel
    for canonical, aliases in VARIABLE_ALIAS_MAP.items():
        group = [canonical] + aliases
        c_in = any(g == c_stem or g in c_raw for g in group)
        r_in = any(g == r_stem or g in r_raw for g in group)
        if c_in and r_in:
            return 0.95

    # Cek pencocokan kompak tanpa spasi (misal 'audit delay' vs 'auditdelay' atau 'kap' di dalam 'ukkap')
    c_compact = c_stem.replace(" ", "")
    r_compact = r_stem.replace(" ", "")
    if c_compact and r_compact and (c_compact == r_compact or (len(c_compact) >= 4 and c_compact in r_compact) or (len(r_compact) >= 4 and r_compact in c_compact)):
        return 0.90

    # Token overlap + SequenceMatcher
    c_tokens = set(c_stem.split())
    r_tokens = set(r_stem.split())
    overlap = len(c_tokens & r_tokens) / max(len(c_tokens | r_tokens), 1)
    seq_ratio = SequenceMatcher(None, c_stem, r_stem).ratio()

    return max(overlap * 0.9, seq_ratio)


def classify_column_header(col_header: str) -> Tuple[Optional[str], float]:
    """Memetakan nama kolom tabel ke salah satu STAT_TYPES kanonik."""
    h = col_header.lower().strip()
    h_clean = re.sub(r"\s+", " ", h)

    for stat_type, synonyms in COLUMN_HEADER_SYNONYMS.items():
        for syn in synonyms:
            if h_clean == syn:
                return stat_type, 1.0
            if len(syn) >= 3 and re.search(rf"\b{re.escape(syn)}\b", h_clean):
                return stat_type, 0.92

    return None, 0.0


# =====================================================================
# 4. EKSTRAKTOR QUAD-TUPLE DARI KALIMAT BAB IV (DEPENDENCY WINDOW BINDER)
# =====================================================================

UNICODE_DASH_PATTERN = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d]")


def normalize_text_dashes(text: str) -> str:
    """Mengubah ragam tanda hubung/dash Unicode (en-dash, em-dash, minus) menjadi hyphen ASCII baku '-'."""
    return UNICODE_DASH_PATTERN.sub("-", text)


NUMBER_TOKEN_REGEX = re.compile(
    r"(?<![A-Za-z0-9_])([+-]?(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d+)?%?|[+-]?[.,]\d+%?)(?![A-Za-z0-9_])"
)


def extract_quad_tuples_from_sentence(
    sentence: str,
    candidate_table_variables: List[str],
    default_variable: Optional[str] = None,
    section_anchor_variable: Optional[str] = None,
) -> List[ClaimQuadTuple]:
    """
    Mengekstrak daftar ClaimQuadTuple <Variabel, Jenis_Statistik, Nilai_Numerik, Desimal>
    dari satu kalimat klaim Bab IV.
    Setiap angka diikat secara lokal ke kata kunci statistik terdekat di sebelah kiri/kanannya
    dan variabel aktif di klausa tersebut dengan pencegahan kebocoran antar-klausa.
    """
    s_norm = normalize_text_dashes(sentence)
    # Pisahkan angka desimal yang menempel ke kata huruf kecil akibat ekstraksi PDF (mis. 76,4dengan -> 76,4 dengan, 0,425yang -> 0,425 yang)
    s_norm = re.sub(r"(\d+[.,]\d+)([a-z]{2,})", r"\1 \2", s_norm)
    s_lower = s_norm.lower()

    # Cek batas klausa utama vs klausa penjelasan/interpretasi
    # Penanda: artinya, yang artinya, yang berarti, berarti, yaitu, yakni, dimana, di mana, hal ini menunjukkan, menunjukkan bahwa, sehingga
    EXPLANATORY_CLAUSE_REGEX = re.compile(
        r'(?:,\s*|\s+)(?:artinya|yang\s+artinya|yang\s+berarti|berarti|yaitu|yakni|dimana|di\s+mana|hal\s+ini\s+menunjukkan|menunjukkan\s+bahwa|sehingga)\b',
        re.IGNORECASE
    )
    expl_m = EXPLANATORY_CLAUSE_REGEX.search(s_norm)
    main_end = expl_m.start() if expl_m else len(s_norm)
    main_clause_text = s_norm[:main_end]
    main_clause_lower = main_clause_text.lower()

    # Normalisasi section_anchor_variable terhadap candidate_table_variables
    effective_section_anchor: Optional[str] = None
    if section_anchor_variable:
        for cv in candidate_table_variables:
            if cv.lower() == section_anchor_variable.lower() or match_variable_row_score(section_anchor_variable, cv) >= 0.70:
                effective_section_anchor = cv
                break
        if not effective_section_anchor:
            effective_section_anchor = section_anchor_variable

    # Prioritas 1A: Cek subjek eksplisit di KLAUSA UTAMA: 'pada variabel X', 'variabel X', 'indikator X'
    explicit_subject_var: Optional[str] = None
    subject_pat = re.search(
        r"(?:pada\s+variabel|variabel|indikator|analisis\s+deskriptif\s+pada\s+variabel|analisis\s+deskriptif\s+pada|pengujian\s+pada)\s+([a-zA-Z\s]{2,35}?)(?:\s+memiliki|\s+menunjukkan|\s+sebesar|\s+dengan|\s+diukur|\s+dihitung|,|\.|\s+adalah)",
        main_clause_lower
    )
    if subject_pat:
        cand_subject = subject_pat.group(1).strip()
        best_subj_sc = 0.0
        for v in candidate_table_variables:
            sc = match_variable_row_score(cand_subject, v)
            if sc > best_subj_sc and sc >= 0.60:
                best_subj_sc = sc
                explicit_subject_var = v

    # 1. Deteksi semua kemunculan variabel kandidat beserta posisinya di kalimat
    var_mentions: List[Tuple[int, int, str]] = []
    for var_name in candidate_table_variables:
        v_stem = normalize_variable_stem(var_name)
        search_terms = {var_name.lower(), v_stem}
        for canonical, aliases in VARIABLE_ALIAS_MAP.items():
            if v_stem == canonical or v_stem in aliases:
                search_terms.update([canonical] + aliases)
        for term in search_terms:
            if len(term) < 2:
                continue
            for m in re.finditer(rf"\b{re.escape(term)}\b", s_lower):
                var_mentions.append((m.start(), m.end(), var_name))

    var_mentions.sort(key=lambda x: x[0])
    main_var_mentions = [vm for vm in var_mentions if vm[1] <= main_end]

    # 2. Deteksi semua jangkar Jenis Statistik beserta posisinya di kalimat
    stat_mentions: List[Tuple[int, int, str]] = []
    for stat_type, patterns in TEXT_STAT_PATTERNS.items():
        for pat in patterns:
            for m in re.finditer(pat, s_lower):
                stat_mentions.append((m.start(), m.end(), stat_type))

    stat_mentions.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    # 2B. Deteksi pola rentang nilai (berkisar antara X sampai Y / antara X sampai Y / berkisar dari X hingga Y)
    RANGE_REGEX = re.compile(
        r"(?:berkisar\s+antara|antara|berkisar\s+dari)\s+([+-]?(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d+)?%?)\s+(?:sampai|hingga|s/d|-|–)\s+([+-]?(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d+)?%?)",
        re.IGNORECASE
    )
    range_stat_map: Dict[Tuple[int, int], str] = {}
    for rm in RANGE_REGEX.finditer(s_norm):
        pre_ctx = s_norm[max(0, rm.start() - 25):rm.start()].lower()
        if "skala" in pre_ctx or "skor" in pre_ctx:
            continue
        range_stat_map[(rm.start(1), rm.end(1))] = "MINIMUM"
        range_stat_map[(rm.start(2), rm.end(2))] = "MAXIMUM"

    # 2C. Deteksi pola pasangan berurutan (tertinggi dan terendah / maksimum dan minimum ... A dan B)
    PAIR_MAX_MIN_REGEX = re.compile(
        r"(?:tertinggi|maksimum)\s+dan\s+(?:terendah|minimum)[^0-9;.\n]{0,80}?([+-]?(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d+)?%?)\s+dan\s+([+-]?(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d+)?%?)",
        re.IGNORECASE
    )
    for rm in PAIR_MAX_MIN_REGEX.finditer(s_norm):
        range_stat_map[(rm.start(1), rm.end(1))] = "MAXIMUM"
        range_stat_map[(rm.start(2), rm.end(2))] = "MINIMUM"

    PAIR_MIN_MAX_REGEX = re.compile(
        r"(?:terendah|minimum)\s+dan\s+(?:tertinggi|maksimum)[^0-9;.\n]{0,80}?([+-]?(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d+)?%?)\s+dan\s+([+-]?(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d+)?%?)",
        re.IGNORECASE
    )
    for rm in PAIR_MIN_MAX_REGEX.finditer(s_norm):
        range_stat_map[(rm.start(1), rm.end(1))] = "MINIMUM"
        range_stat_map[(rm.start(2), rm.end(2))] = "MAXIMUM"

    # Batas klausa konjungsi kontrastif untuk Atomic Clause Splitting
    contrast_splits = [0]
    for cm in re.finditer(r"(?:,\s*|\s+)(?:sedangkan|sementara\s+itu|berbeda\s+dengan|adapun)\b|;\s*", s_lower):
        contrast_splits.append(cm.start())
    contrast_splits.append(len(s_norm))

    # 3. Ekstrak semua token numerik (kecuali nomor Tabel/Bab/Halaman seperti 'Tabel 4.2' dan penomoran sub-bab)
    ignored_spans: List[Tuple[int, int]] = []
    for m in re.finditer(r"\b(?:tabel|table|gambar|bab|halaman|hal\.?|lampiran|persamaan|uji|model)\s+\d+(?:[.,]\d+)*", s_lower):
        ignored_spans.append((m.start(), m.end()))
    for m in re.finditer(r"\b\d+(?:\.\d+){2,}\b", s_lower):
        ignored_spans.append((m.start(), m.end()))
    for m in re.finditer(r"^\s*\d+(?:\.\d+)+\s+", s_lower):
        ignored_spans.append((m.start(), m.end()))
    for m in re.finditer(r"(?:\(\s*[xyz]\s*\d+\s*\)|\b(?:x|y|z|hipotesis|h)\s*\d+\b)", s_lower):
        ignored_spans.append((m.start(), m.end()))

    quad_tuples: List[ClaimQuadTuple] = []

    for m in NUMBER_TOKEN_REGEX.finditer(s_norm):
        c_start, c_end = m.start(), m.end()
        if any(ig_s <= c_start and c_end <= ig_e for ig_s, ig_e in ignored_spans):
            continue

        raw_num = m.group(1)

        # Filter semantik: abaikan token non-statistika (tahun sitasi, rentang tahun, nomor indeks, skala Likert, threshold aturan, dsb.)
        span_type = classify_numeric_span(s_norm, c_start, c_end, raw_num)
        if span_type != "STAT_METRIC":
            continue

        parsed = parse_academic_number(raw_num)
        if parsed is None:
            continue
        val, dec, is_pct = parsed

        # Abaikan angka ambang batas baku (0.05, 0.01, 0.10, 0.1, 10.0) jika didahului penanda pembanding atau kriteria uji
        if round(val, 4) in (0.05, 0.01, 0.1, 10.0):
            left_45 = s_lower[max(0, c_start - 45):c_start]
            if re.search(r"(?:lebih\s+besar(?:\s+dari)?|lebih\s+kecil(?:\s+dari)?|di\s+atas|di\s+bawah|kurang\s+dari|melebihi|alpha|α|taraf\s+signifikansi|tingkat\s+signifikansi|batas\s+kritis|ambang|>=|<=|>|<)\s*(?:pada|sebesar|=)?\s*$", left_45):
                continue

        # Cek operator pertidaksamaan tepat di sebelah kiri angka (18 karakter)
        left_ctx = s_norm[max(0, c_start - 18):c_start].lower().strip()
        op = "EQ"
        if re.search(r"(?:>=|minimal|paling\s+sedikit)\s*$", left_ctx):
            op = "GTE"
        elif re.search(r"(?:>|lebih\s+dari|di\s+atas)\s*$", left_ctx):
            op = "GT"
        elif re.search(r"(?:<=|maksimal|paling\s+banyak)\s*$", left_ctx):
            op = "LTE"
        elif re.search(r"(?:<|kurang\s+dari|di\s+bawah)\s*$", left_ctx):
            op = "LT"

        # Cek jika angka merupakan batas rentang nilai atau pasangan berurutan
        best_stat: Optional[str] = None
        if (c_start, c_end) in range_stat_map:
            best_stat = range_stat_map[(c_start, c_end)]
        else:
            for (rs, re_span), r_stat in range_stat_map.items():
                if rs <= c_start and c_end <= re_span:
                    best_stat = r_stat
                    break

        # Cari Jenis Statistik terdekat: utamakan di sebelah kiri angka (jarak <= 85 char)
        if best_stat is None:
            best_dist = 9999
            for st_start, st_end, st_type in stat_mentions:
                if st_start <= c_start:
                    dist = c_start - st_end
                    between_text = s_norm[st_end:c_start]
                    # Kata apositif (yaitu, yakni, adalah, sebesar) dan simbol operator pertidaksamaan
                    # tidak boleh memutus ikatan statistik ke angka berikutnya
                    has_sentence_break = bool(re.search(r"[;]|\.\s+[A-Z]", between_text)) or "artinya" in between_text.lower()
                    if dist <= 85 and not has_sentence_break:
                        if dist < best_dist:
                            best_dist = dist
                            best_stat = st_type

        # Jika di sebelah kiri belum ada, cari di sebelah kanan (kalimat pasif/inversi: "sebesar X tercatat sebagai Y")
        if best_stat is None:
            blocked_right_words = ("artinya", "yaitu", "dapat", "selisih", "dibanding", "sedangkan", "sehingga", "karena")
            for st_start, st_end, st_type in stat_mentions:
                if st_start >= c_end:
                    dist = st_start - c_end
                    between_text = s_norm[c_end:st_start]
                    b_lower = between_text.lower()
                    if dist <= 45 and ";" not in between_text and "." not in between_text and "," not in between_text:
                        if not any(bw in b_lower for bw in blocked_right_words):
                            if dist < best_dist:
                                best_dist = dist
                                best_stat = st_type

        if best_stat is None and is_pct:
            best_stat = "PERCENTAGE"

        if best_stat is None:
            continue

        # Atomic Clause Variable Resolution: tentukan klausa aktif untuk angka ini
        cur_clause_start = 0
        cur_clause_end = len(s_norm)
        for i in range(len(contrast_splits) - 1):
            if contrast_splits[i] <= c_start < contrast_splits[i + 1]:
                cur_clause_start = contrast_splits[i]
                cur_clause_end = contrast_splits[i + 1]
                break

        # Variabel yang muncul di klausa atomik sebelum batas klausa penjelas
        clause_main_vars = [
            vm for vm in main_var_mentions
            if cur_clause_start <= vm[0] < cur_clause_end
        ]

        active_var: Optional[str] = None

        # Prioritas 1: KLAUSA UTAMA
        # 1A. Variabel di dalam klausa atomik yang berada sebelum angka
        if clause_main_vars:
            closest_v_dist = 9999
            for v_start, v_end, v_name in clause_main_vars:
                if v_start <= c_start:
                    dist = c_start - v_end
                    if dist < closest_v_dist:
                        closest_v_dist = dist
                        active_var = v_name
            if active_var is None:
                active_var = clause_main_vars[0][2]

        # 1B. Variabel terdekat di klausa utama dalam jarak <= 8 kata sebelum angka
        if active_var is None and main_var_mentions:
            min_w_dist = 9999
            for v_start, v_end, v_name in main_var_mentions:
                if v_start <= c_start:
                    between_str = s_norm[v_end:c_start]
                    w_dist = len(between_str.split())
                    if w_dist <= 8 and w_dist < min_w_dist:
                        min_w_dist = w_dist
                        active_var = v_name

        # 1C. Subjek eksplisit di klausa utama (mis. 'analisis deskriptif pada variabel X')
        if active_var is None and explicit_subject_var:
            active_var = explicit_subject_var

        # 1D. Jika angka berada di dalam klausa utama dan ada variabel di klausa utama
        if active_var is None and c_start < main_end and main_var_mentions:
            active_var = main_var_mentions[0][2]

        # Prioritas 2: Section-heading anchor variable (mis. '4.2.1.4 Likuiditas')
        if active_var is None and effective_section_anchor:
            active_var = effective_section_anchor

        # Prioritas 3: Discourse cache kalimat sebelumnya (default_variable)
        if active_var is None and default_variable:
            active_var = default_variable

        # Fallback terakhir: jika dan hanya jika Prioritas 1, 2, dan 3 sama sekali tidak ada
        if active_var is None and var_mentions:
            closest_v_dist = 9999
            for v_start, v_end, v_name in var_mentions:
                if v_start <= c_start:
                    dist = c_start - v_end
                    if dist < closest_v_dist:
                        closest_v_dist = dist
                        active_var = v_name
            if active_var is None:
                active_var = var_mentions[0][2]

        if active_var is None:
            continue

        quad_tuples.append(
            ClaimQuadTuple(
                sentence_text=sentence,
                variable_name=active_var,
                stat_type=best_stat,
                numeric_value=val,
                decimal_places=dec,
                raw_number_str=raw_num,
                is_percentage=is_pct,
                operator=op,
                extraction_confidence=0.95,
            )
        )

    # 4. Hybrid Fallback: Jika aturan deterministik belum mengikat statistik
    # Dipanggil hanya jika eksplisit diaktifkan via env LOCUS_ENABLE_GLINER=1 agar audit tetap instan (<4 detik)
    if not quad_tuples and os.environ.get("LOCUS_ENABLE_GLINER", "0") == "1":
        has_number = bool(re.search(r"\d", sentence))
        has_var = bool(default_variable) or bool(explicit_subject_var) or len(var_mentions) > 0 or any(
            re.search(rf"\b{re.escape(normalize_variable_stem(v))}\b", s_lower)
            for v in candidate_table_variables if len(normalize_variable_stem(v)) >= 3
        )
        if has_number and has_var:
            target_var = explicit_subject_var or default_variable
            fallback_extractor = GlinerHybridFallbackExtractor.get_instance()
            fallback_quads = fallback_extractor.extract_fallback_quads(
                sentence=sentence,
                candidate_table_variables=candidate_table_variables,
                default_variable=target_var
            )
            if fallback_quads:
                return fallback_quads

    return quad_tuples


# =====================================================================
# 4B. HYBRID FALLBACK: NEURAL GLiNER EXTRACTOR (OFFLINE CPU)
# =====================================================================

class GlinerHybridFallbackExtractor:
    """
    Jalur Fallback Neural: Dipanggil HANYA jika aturan deterministik gagal
    mengikat jenis statistik pada kalimat pasif / inversi yang kompleks.
    Memuat model dari 'data/models/gliner_multi-v2.1' (local_files_only=True).
    """
    _instance: Optional["GlinerHybridFallbackExtractor"] = None
    _model = None
    _init_attempted: bool = False

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir

    def _ensure_model_loaded(self):
        if GlinerHybridFallbackExtractor._init_attempted:
            return
        GlinerHybridFallbackExtractor._init_attempted = True
        try:
            import logging
            logging.getLogger("transformers").setLevel(logging.ERROR)
            from gliner import GLiNER
            if self.model_dir is None:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                self.model_dir = os.path.join(base_dir, "data", "models", "gliner_multi-v2.1")

            onnx_path = os.path.join(self.model_dir, "model.onnx")
            if os.path.exists(onnx_path):
                GlinerHybridFallbackExtractor._model = GLiNER.from_pretrained(
                    self.model_dir,
                    load_onnx_model=True,
                    local_files_only=True
                )
            elif os.path.exists(os.path.join(self.model_dir, "model.safetensors")):
                GlinerHybridFallbackExtractor._model = GLiNER.from_pretrained(
                    self.model_dir,
                    local_files_only=True
                )
        except Exception:
            GlinerHybridFallbackExtractor._model = None

    @classmethod
    def get_instance(cls, model_dir: Optional[str] = None) -> "GlinerHybridFallbackExtractor":
        if cls._instance is None:
            cls._instance = GlinerHybridFallbackExtractor(model_dir)
        return cls._instance

    def extract_fallback_quads(
        self,
        sentence: str,
        candidate_table_variables: List[str],
        default_variable: Optional[str] = None,
    ) -> List[ClaimQuadTuple]:
        # 1. Jalur Cepat Bidirectional Inverted Heuristic (< 0.1 ms)
        heuristic_quads = self._heuristic_inverted_fallback(sentence, candidate_table_variables, default_variable)
        if heuristic_quads:
            return heuristic_quads

        # 2. Filter kalimat tanpa indikator statistik atau pengukuran
        s_lower = sentence.lower()
        stat_cues = [
            "rata", "mean", "rerata", "minimum", "maksimum", "terkecil", "terendah",
            "terbesar", "tertinggi", "standar", "deviasi", "simpangan", "baku",
            "skor", "nilai", "koefisien", "f1", "akurasi", "presisi", "recall", "uji", "sebesar"
        ]
        if not any(cue in s_lower for cue in stat_cues):
            return []

        # 3. Lazy load Neural GLiNER HANYA jika sintaksis belum tertangkap pola baku
        self._ensure_model_loaded()
        if GlinerHybridFallbackExtractor._model is None:
            return []

        labels = ["nama variabel", "jenis statistik", "nilai numerik"]
        try:
            entities = GlinerHybridFallbackExtractor._model.predict_entities(
                sentence,
                labels,
                threshold=0.30
            )
        except Exception:
            return []

        var_texts = [e["text"] for e in entities if e["label"] == "nama variabel"]
        stat_texts = [e["text"] for e in entities if e["label"] == "jenis statistik"]

        chosen_var = default_variable
        if not chosen_var and var_texts:
            for vt in var_texts:
                for c_var in candidate_table_variables:
                    if match_variable_row_score(vt, c_var) >= 0.55:
                        chosen_var = c_var
                        break
                if chosen_var:
                    break
            if not chosen_var and candidate_table_variables:
                chosen_var = candidate_table_variables[0]
            elif not chosen_var and var_texts:
                chosen_var = var_texts[0]

        chosen_stat = None
        for st in stat_texts:
            for s_type, patterns in TEXT_STAT_PATTERNS.items():
                for pat in patterns:
                    if re.search(pat, st, re.IGNORECASE):
                        chosen_stat = s_type
                        break
                if chosen_stat:
                    break
            if not chosen_stat:
                mapped, _ = classify_column_header(st)
                if mapped:
                    chosen_stat = mapped
            if chosen_stat:
                break

        if not chosen_stat or not chosen_var:
            return self._heuristic_inverted_fallback(sentence, candidate_table_variables, default_variable)

        quads: List[ClaimQuadTuple] = []
        for m in NUMBER_TOKEN_REGEX.finditer(sentence):
            raw_num = m.group(1)
            parsed = parse_academic_number(raw_num)
            if parsed is None:
                continue
            val, dec, is_pct = parsed
            quads.append(
                ClaimQuadTuple(
                    sentence_text=sentence,
                    variable_name=chosen_var,
                    stat_type=chosen_stat,
                    numeric_value=val,
                    decimal_places=dec,
                    raw_number_str=raw_num,
                    is_percentage=is_pct,
                    extraction_confidence=0.88,
                )
            )
        return quads

    def _heuristic_inverted_fallback(
        self,
        sentence: str,
        candidate_table_variables: List[str],
        default_variable: Optional[str] = None,
    ) -> List[ClaimQuadTuple]:
        """
        Bidirectional scan untuk kalimat pasif / inversi (angka di depan, statistik di belakang).
        """
        s_norm = normalize_text_dashes(sentence)
        s_lower = s_norm.lower()

        stat_mentions: List[Tuple[int, int, str]] = []
        for stat_type, patterns in TEXT_STAT_PATTERNS.items():
            for pat in patterns:
                for m in re.finditer(pat, s_lower):
                    stat_mentions.append((m.start(), m.end(), stat_type))

        if not stat_mentions:
            return []

        stat_mentions.sort(key=lambda x: (x[0], -(x[1] - x[0])))

        active_var = default_variable
        if not active_var:
            best_score = 0.0
            for v_name in candidate_table_variables:
                score = match_variable_row_score(s_lower, v_name)
                if score > best_score and score >= 0.55:
                    best_score = score
                    active_var = v_name

        if not active_var and candidate_table_variables:
            active_var = candidate_table_variables[0]

        if not active_var:
            return []

        ignored_spans: List[Tuple[int, int]] = []
        for m in re.finditer(r"\b(?:tabel|table|gambar|bab|halaman|hal\.?|lampiran|persamaan|uji|model)\s+\d+(?:[.,]\d+)*", s_lower):
            ignored_spans.append((m.start(), m.end()))
        for m in re.finditer(r"\b\d+(?:\.\d+){2,}\b", s_lower):
            ignored_spans.append((m.start(), m.end()))
        for m in re.finditer(r"^\s*\d+(?:\.\d+)+\s+", s_lower):
            ignored_spans.append((m.start(), m.end()))

        quads: List[ClaimQuadTuple] = []
        for m in NUMBER_TOKEN_REGEX.finditer(s_norm):
            c_start, c_end = m.start(), m.end()
            if any(isp[0] <= c_start and c_end <= isp[1] for isp in ignored_spans):
                continue

            raw_num = m.group(1)
            parsed = parse_academic_number(raw_num)
            if parsed is None:
                continue

            best_stat = None
            best_dist = 999999
            for sm_start, sm_end, s_type in stat_mentions:
                if sm_end <= c_start:
                    dist = c_start - sm_end
                elif c_end <= sm_start:
                    dist = sm_start - c_end
                else:
                    dist = 0
                if dist < best_dist and dist <= 120:
                    best_dist = dist
                    best_stat = s_type

            if not best_stat:
                continue

            val, dec, is_pct = parsed
            quads.append(
                ClaimQuadTuple(
                    sentence_text=sentence,
                    variable_name=active_var,
                    stat_type=best_stat,
                    numeric_value=val,
                    decimal_places=dec,
                    raw_number_str=raw_num,
                    is_percentage=is_pct,
                    extraction_confidence=0.85,
                )
            )
        return quads


# =====================================================================
# 5. MESIN TOLERANSI PEMBULATAN & VERIFIKASI SEL 2-SUMBU
# =====================================================================

def check_rounding_and_truncation(
    claim_val: float,
    claim_decimals: int,
    cell_val: float,
    cell_decimals: int,
    is_claim_pct: bool = False,
    stat_type: str = "",
) -> Tuple[str, float, float, float]:
    """
    Membandingkan nilai klaim terhadap nilai sel dengan memperhitungkan:
    1. Penyesuaian skala proporsi <-> persentase (0.7857 <-> 78.57%)
    2. Toleransi pembulatan simetris statcheck: [x - 0.5*10^-d, x + 0.5*10^-d]
    3. Toleransi pemotongan desimal SPSS/Excel (truncation tanpa pembulatan ke atas)
    """
    effective_cell = cell_val
    if (is_claim_pct or stat_type == "PERCENTAGE") and 0.0 < abs(cell_val) <= 1.0 and abs(claim_val) > 1.0:
        effective_cell = cell_val * 100.0
    elif not is_claim_pct and 0.0 < abs(claim_val) <= 1.0 and 1.0 < abs(cell_val) <= 100.0 and stat_type == "PERCENTAGE":
        effective_cell = cell_val / 100.0

    target_d = min(claim_decimals, cell_decimals) if cell_decimals > 0 else claim_decimals
    half_unit = 0.5 * (10.0 ** (-claim_decimals))
    eps = 1e-9

    lower_bound = claim_val - half_unit - eps
    upper_bound = claim_val + half_unit + eps

    # 1. Cek kecocokan eksak
    if abs(claim_val - effective_cell) <= 1e-7:
        return "VALID_EXACT", effective_cell, lower_bound, upper_bound

    # 2. Cek kecocokan pembulatan simetris
    if lower_bound <= effective_cell <= upper_bound:
        return "VALID_ROUNDED", effective_cell, lower_bound, upper_bound

    # 3. Cek kecocokan sebaliknya jika tabel yang dibulatkan lebih pendek dari klaim
    if cell_decimals < claim_decimals:
        cell_half = 0.5 * (10.0 ** (-cell_decimals))
        if (effective_cell - cell_half - eps) <= claim_val <= (effective_cell + cell_half + eps):
            return "VALID_ROUNDED", effective_cell, effective_cell - cell_half, effective_cell + cell_half

    # 4. Cek pemotongan desimal (Truncation / Flooring)
    factor = 10.0 ** claim_decimals
    truncated_cell = math.trunc(effective_cell * factor) / factor
    if abs(claim_val - truncated_cell) <= 1e-7:
        return "TRUNCATION_WARNING", effective_cell, lower_bound, upper_bound

    return "VALUE_MISMATCH", effective_cell, lower_bound, upper_bound


def verify_quad_tuple_against_table(
    quad: ClaimQuadTuple,
    table_headers: List[str],
    table_rows: List[List[str]],
    min_row_score: float = 0.78,
    min_col_score: float = 0.80,
) -> QuadVerificationResult:
    """
    Memverifikasi satu ClaimQuadTuple terhadap sebuah tabel:
    - Sumbu Y: Cari baris dengan Nama Variabel terbaik (>= min_row_score)
    - Sumbu X: Cari kolom dengan Jenis Statistik yang sesuai (>= min_col_score)
    - Sel (Y, X): Bandingkan Nilai Numerik dengan Toleransi Pembulatan
    - Diagnostik Kolom: Jika tidak cocok, periksa apakah penulis salah baca kolom di baris yang sama.
    """
    # Hard Guard Anti-Tahun: jika nilai numerik berupa bilangan bulat 1900..2099
    # dan kolom bukan tahun/year/periode, kembalikan UNLINKED_SKIP
    if 1900 <= quad.numeric_value <= 2099 and float(quad.numeric_value).is_integer():
        is_year_col = any(
            re.search(r"\b(?:tahun|year|periode|thn)\b", h.lower()) for h in table_headers
        )
        if not is_year_col:
            return QuadVerificationResult(
                status="UNLINKED_SKIP",
                quad=quad,
                explanation_id=f"Angka {quad.raw_number_str} terdeteksi sebagai tahun/periode, bukan metrik statistik tabel."
            )

    best_row_idx = -1
    best_row_score = 0.0
    best_row_label = ""

    for r_idx, row in enumerate(table_rows):
        if not row:
            continue
        row_label = row[0].strip()
        if row_label.isdigit() and len(row) > 1:
            row_label = row[1].strip()

        score = match_variable_row_score(quad.variable_name, row_label)
        if score > best_row_score:
            best_row_score = score
            best_row_idx = r_idx
            best_row_label = row_label

    if best_row_idx == -1 or best_row_score < min_row_score:
        return QuadVerificationResult(
            status="UNLINKED_SKIP",
            quad=quad,
            row_confidence=best_row_score,
            explanation_id=(
                f"Variabel '{quad.variable_name}' tidak ditemukan pada baris tabel ini "
                f"(skor tertinggi: {best_row_score:.2f} < {min_row_score}). Pemeriksaan dilewati untuk mencegah false alarm."
            ),
        )

    best_col_idx = -1
    best_col_score = 0.0
    best_col_label = ""

    for c_idx, col_name in enumerate(table_headers):
        mapped_type, c_score = classify_column_header(col_name)
        if mapped_type == quad.stat_type and c_score > best_col_score:
            best_col_score = c_score
            best_col_idx = c_idx
            best_col_label = col_name

    if best_col_idx == -1 or best_col_score < min_col_score:
        return QuadVerificationResult(
            status="UNLINKED_SKIP",
            quad=quad,
            matched_row_label=best_row_label,
            row_confidence=best_row_score,
            col_confidence=best_col_score,
            explanation_id=(
                f"Tabel memiliki baris '{best_row_label}', namun tidak memiliki kolom untuk statistik "
                f"'{quad.stat_type}'. Pemeriksaan dilewati agar tidak salah membandingkan antar-kolom."
            ),
        )

    target_row = table_rows[best_row_idx]
    if best_col_idx >= len(target_row):
        return QuadVerificationResult(
            status="UNLINKED_SKIP",
            quad=quad,
            matched_row_label=best_row_label,
            matched_col_label=best_col_label,
            explanation_id="Indeks kolom berada di luar panjang sel baris tabel.",
        )

    raw_cell_str = target_row[best_col_idx].strip()
    parsed_cell = parse_academic_number(raw_cell_str)
    if parsed_cell is None:
        return QuadVerificationResult(
            status="UNLINKED_SKIP",
            quad=quad,
            matched_row_label=best_row_label,
            matched_col_label=best_col_label,
            table_cell_raw=raw_cell_str,
            explanation_id=f"Sel ({best_row_label}, {best_col_label}) berisi teks non-numerik '{raw_cell_str}'.",
        )

    cell_val, cell_dec, _ = parsed_cell

    quad_op = getattr(quad, "operator", "EQ")
    if quad_op != "EQ":
        eff_cell_val = cell_val
        if (quad.is_percentage or quad.stat_type == "PERCENTAGE") and 0.0 < abs(cell_val) <= 1.0 and abs(quad.numeric_value) > 1.0:
            eff_cell_val = cell_val * 100.0
        elif not quad.is_percentage and 0.0 < abs(quad.numeric_value) <= 1.0 and 1.0 < abs(cell_val) <= 100.0 and quad.stat_type == "PERCENTAGE":
            eff_cell_val = cell_val / 100.0

        is_satisfied = False
        op_sym = "="
        if quad_op == "GT":
            is_satisfied = (eff_cell_val > quad.numeric_value)
            op_sym = ">"
        elif quad_op == "GTE":
            is_satisfied = (eff_cell_val >= quad.numeric_value - 1e-9)
            op_sym = ">="
        elif quad_op == "LT":
            is_satisfied = (eff_cell_val < quad.numeric_value)
            op_sym = "<"
        elif quad_op == "LTE":
            is_satisfied = (eff_cell_val <= quad.numeric_value + 1e-9)
            op_sym = "<="

        if is_satisfied:
            return QuadVerificationResult(
                status="VALID_EXACT",
                quad=quad,
                matched_row_label=best_row_label,
                matched_col_label=best_col_label,
                row_confidence=best_row_score,
                col_confidence=best_col_score,
                table_cell_raw=raw_cell_str,
                table_cell_value=eff_cell_val,
                explanation_id=(
                    f"COCOK PERTIDAKSAMAAN: Nilai sel ({best_row_label}, {best_col_label}) = {raw_cell_str} "
                    f"memenuhi klaim batas {quad.stat_type} {op_sym} {quad.raw_number_str}."
                ),
            )
        else:
            return QuadVerificationResult(
                status="VALUE_MISMATCH",
                quad=quad,
                matched_row_label=best_row_label,
                matched_col_label=best_col_label,
                row_confidence=best_row_score,
                col_confidence=best_col_score,
                table_cell_raw=raw_cell_str,
                table_cell_value=eff_cell_val,
                explanation_id=(
                    f"PERTIDAKSAMAAN TIDAK TERPENUHI: Nilai sel ({best_row_label}, {best_col_label}) = {raw_cell_str} "
                    f"tidak memenuhi klaim batas {quad.stat_type} {op_sym} {quad.raw_number_str}."
                ),
            )

    verdict, eff_cell_val, low_b, high_b = check_rounding_and_truncation(
        claim_val=quad.numeric_value,
        claim_decimals=quad.decimal_places,
        cell_val=cell_val,
        cell_decimals=cell_dec,
        is_claim_pct=quad.is_percentage,
        stat_type=quad.stat_type,
    )

    if verdict in ("VALID_EXACT", "VALID_ROUNDED"):
        return QuadVerificationResult(
            status=verdict,
            quad=quad,
            matched_row_label=best_row_label,
            matched_col_label=best_col_label,
            row_confidence=best_row_score,
            col_confidence=best_col_score,
            table_cell_raw=raw_cell_str,
            table_cell_value=eff_cell_val,
            allowed_lower_bound=low_b,
            allowed_upper_bound=high_b,
            explanation_id=(
                f"COCOK ({verdict}): Klaim [{quad.variable_name} | {quad.stat_type} = {quad.raw_number_str}] "
                f"sesuai dengan sel ({best_row_label}, {best_col_label}) = {raw_cell_str} "
                f"dalam rentang toleransi pembulatan [{low_b:.4f}, {high_b:.4f}]."
            ),
        )

    if verdict == "TRUNCATION_WARNING":
        rounded_proper = round(eff_cell_val, quad.decimal_places)
        return QuadVerificationResult(
            status="TRUNCATION_WARNING",
            quad=quad,
            matched_row_label=best_row_label,
            matched_col_label=best_col_label,
            row_confidence=best_row_score,
            col_confidence=best_col_score,
            table_cell_raw=raw_cell_str,
            table_cell_value=eff_cell_val,
            allowed_lower_bound=low_b,
            allowed_upper_bound=high_b,
            explanation_id=(
                f"PERINGATAN PEMOTONGAN DESIMAL: Klaim menulis {quad.stat_type} '{quad.variable_name}' = {quad.raw_number_str} "
                f"(hasil potong langsung dari sel {raw_cell_str}). Menurut aturan pembulatan baku {quad.decimal_places} desimal, "
                f"seharusnya ditulis {rounded_proper:.{quad.decimal_places}f}."
            ),
        )

    swapped_col_name: Optional[str] = None
    for other_c_idx, other_raw in enumerate(target_row):
        if other_c_idx == best_col_idx or other_c_idx >= len(table_headers):
            continue
        other_parsed = parse_academic_number(other_raw)
        if other_parsed is None:
            continue
        other_val, other_dec, _ = other_parsed
        other_verdict, _, _, _ = check_rounding_and_truncation(
            claim_val=quad.numeric_value,
            claim_decimals=quad.decimal_places,
            cell_val=other_val,
            cell_decimals=other_dec,
            is_claim_pct=quad.is_percentage,
            stat_type=quad.stat_type,
        )
        if other_verdict in ("VALID_EXACT", "VALID_ROUNDED", "TRUNCATION_WARNING"):
            swapped_col_name = table_headers[other_c_idx]
            break

    if swapped_col_name:
        return QuadVerificationResult(
            status="COLUMN_SWAP_ERROR",
            quad=quad,
            matched_row_label=best_row_label,
            matched_col_label=best_col_label,
            row_confidence=best_row_score,
            col_confidence=best_col_score,
            table_cell_raw=raw_cell_str,
            table_cell_value=eff_cell_val,
            allowed_lower_bound=low_b,
            allowed_upper_bound=high_b,
            swapped_column_found=swapped_col_name,
            explanation_id=(
                f"SALAH BACA KOLOM (COLUMN SWAP): Klaim menyatakan {quad.stat_type} dari '{quad.variable_name}' "
                f"adalah {quad.raw_number_str}. Padahal pada tabel, sel ({best_row_label}, {best_col_label}) bernilai {raw_cell_str}. "
                f"Angka {quad.raw_number_str} justru ditemukan pada kolom '{swapped_col_name}' di baris yang sama!"
            ),
        )

    return QuadVerificationResult(
        status="VALUE_MISMATCH",
        quad=quad,
        matched_row_label=best_row_label,
        matched_col_label=best_col_label,
        row_confidence=best_row_score,
        col_confidence=best_col_score,
        table_cell_raw=raw_cell_str,
        table_cell_value=eff_cell_val,
        allowed_lower_bound=low_b,
        allowed_upper_bound=high_b,
        explanation_id=(
            f"INKONSISTENSI NILAI SEL: Klaim menyatakan {quad.stat_type} untuk variabel '{quad.variable_name}' "
            f"adalah {quad.raw_number_str}, namun pada tabel sel ({best_row_label}, {best_col_label}) tercatat sebesar {raw_cell_str} "
            f"(di luar rentang toleransi pembulatan [{low_b:.4f}, {high_b:.4f}])."
        ),
    )
