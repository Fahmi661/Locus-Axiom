"""
LOCUS v3.4 - SPSS Likert Frequency Table Parser & Fast Explicit Table-ID Router
Lisensi: MIT / Apache-2.0 (100% Offline, <4 Detik untuk 53 Halaman Bab IV)
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any


# Urutan dari frasa paling panjang/spesifik agar "sangat tidak setuju" tidak tertangkap sebagai "setuju"
LIKERT_TEXT_TO_CODE: List[Tuple[str, List[str]]] = [
    ("STS", [
        r"sangat\s+tidak\s+setuju",
        r"sangat\s+tidak\s+puas",
        r"sangat\s+tidak\s+baik",
        r"sangat\s+rendah",
        r"\bsts\b",
    ]),
    ("TS", [
        r"(?<!sangat\s)tidak\s+setuju",
        r"(?<!sangat\s)tidak\s+puas",
        r"(?<!sangat\s)tidak\s+baik",
        r"\bts\b",
    ]),
    ("SS", [
        r"sangat\s+setuju",
        r"sangat\s+puas",
        r"sangat\s+baik",
        r"sangat\s+tinggi",
        r"\bss\b",
    ]),
    ("N", [
        r"kurang\s+setuju",
        r"ragu\s*-\s*ragu",
        r"\bnetral\b",
        r"cukup\s+setuju",
        r"cukup\s+baik",
        r"\bks\b",
        r"\brr\b",
    ]),
    ("S", [
        r"(?<!sangat\s)(?<!tidak\s)(?<!kurang\s)(?<!cukup\s)\bsetuju\b",
        r"(?<!sangat\s)(?<!tidak\s)\bpuas\b",
        r"\bs\b",
    ]),
    ("TOTAL", [
        r"(?<!dari\s)(?<!seluruh\s)\btotal\s+responden\b",
        r"(?<!dari\s)(?<!seluruh\s)\bjumlah\s+keseluruhan\b",
        r"(?<!dari\s)(?<!seluruh\s)\btotal\s+keseluruhan\b",
    ]),
]

LIKERT_ROW_ALIASES: Dict[str, List[str]] = {
    "STS": ["sts", "sangat tidak setuju", "1", "1.0", "sangat tidak baik", "sangat tidak puas"],
    "TS": ["ts", "tidak setuju", "2", "2.0", "tidak baik", "tidak puas"],
    "N": ["n", "ks", "rr", "netral", "kurang setuju", "ragu-ragu", "ragu", "cukup", "3", "3.0"],
    "S": ["s", "setuju", "4", "4.0", "baik", "puas"],
    "SS": ["ss", "sangat setuju", "5", "5.0", "sangat baik", "sangat puas"],
    "TOTAL": ["total", "jumlah", "total responden"],
}

LIKERT_HUMAN_LABEL: Dict[str, str] = {
    "STS": "Sangat Tidak Setuju (STS)",
    "TS": "Tidak Setuju (TS)",
    "N": "Netral / Kurang Setuju (N/KS)",
    "S": "Setuju (S)",
    "SS": "Sangat Setuju (SS)",
    "TOTAL": "Total Responden",
}

ROMAN_TO_INT: Dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8
}


def normalize_table_id(text: str) -> Optional[str]:
    """Mengubah 'Tabel IV.21', 'tabel 4.21', 'Tabel_4_3', 'Tabel IV.3' menjadi ID kanonik '4.21', '4.3'."""
    if not text:
        return None
    normalized_text = re.sub(r"_+", " ", str(text))
    m = re.search(
        r"\b(?:tabel|table)\s+([IVX]+|\d+)\s*[.\-\s]\s*(\d+)\b",
        normalized_text,
        flags=re.IGNORECASE,
    )
    if not m:
        # Juga tangani format satu digit misal 'Tabel 3' atau 'Tabel IV'
        m_single = re.search(r"\b(?:tabel|table)\s+([IVX]+|\d+)\b", normalized_text, flags=re.IGNORECASE)
        if m_single:
            val_raw = m_single.group(1).upper()
            return str(ROMAN_TO_INT.get(val_raw, val_raw))
        return None
    major_raw, minor_raw = m.group(1).upper(), m.group(2)
    major_num = ROMAN_TO_INT.get(major_raw, major_raw)
    return f"{major_num}.{int(minor_raw)}"


def route_claim_to_exact_table(
    sentence: str,
    claim_page: int,
    claim_y_top: float,
    all_tables: List[Dict],
) -> Optional[Dict]:
    """
    Mengunci klaim ke tabel yang tepat secara O(1) TANPA memindai seluruh dokumen:
    1. Jika kalimat menyebut 'Menurut tabel IV.21...', langsung kunci ke tabel dengan ID '4.21'.
       Jika ID eksplisit tidak ditemukan di all_tables, kembalikan None (abstain)!
    2. Jika tidak menyebut nomor tabel, pilih tabel tepat di atas paragraf (y_bottom <= claim_y_top + 25)
       dengan jarak vertikal terkecil.
    """
    explicit_id = normalize_table_id(sentence)
    if explicit_id:
        candidates = [t for t in all_tables if t.get("normalized_id") == explicit_id]
        if candidates:
            candidates.sort(key=lambda t: abs(t.get("page", 0) - claim_page))
            return candidates[0]
        # JANGAN pernah fallback ke tabel lain jika kalimat menyebut ID tabel eksplisit!
        return None

    # Jika tidak ada ID eksplisit, pilih tabel yang y_bottom <= claim_y_top + 25 dengan jarak vertikal terkecil
    same_page_tables = []
    for t in all_tables:
        if t.get("page") == claim_page:
            y_bot = t.get("y_bottom") or (t.get("bbox", [0, 0, 0, 0])[3] if len(t.get("bbox", [])) >= 4 else 0.0)
            if y_bot <= claim_y_top + 25.0:
                dist = abs(claim_y_top - y_bot)
                same_page_tables.append((dist, t))

    if same_page_tables:
        same_page_tables.sort(key=lambda item: item[0])
        return same_page_tables[0][1]

    return None


def resolve_table_with_ref_check(
    sentence: str,
    claim_page: int,
    claim_y_top: float,
    all_tables: List[Dict],
    scope_table_id: Optional[str] = None,
    next_table_id: Optional[str] = None,
    active_discussion_table_id: Optional[str] = None,
) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Menyelesaikan target tabel untuk sebuah klaim dengan isolasi teritorial tabel & pengecekan salah ketik rujukan:
    1. Cari local_table: tabel dengan table_id == scope_table_id, atau tabel terdekat di atas claim_y_top
       pada halaman yang sama (atau tabel terakhir halaman sebelumnya jika klaim di puncak halaman).
    2. Jika kalimat adalah pengantar ke bawah ('sebagai berikut', 'di bawah ini') tanpa ID eksplisit,
       utamakan next_table_id (tabel tepat di bawah paragraf).
    3. Cari explicit_id = normalize_table_id(sentence) dan explicit_table yang cocok.
    4. Jika explicit_table dan local_table BERBEDA: hitung kecocokan pasangan (kategori/baris, nilai)
       secara kontekstual (khususnya untuk tabel Likert SPSS) agar angka kebetulan/tahun/kumulatif
       tidak menipu detektor salah rujuk.
    5. Jika local_table tidak tersedia dan tidak ada ID eksplisit, gunakan active_discussion_table_id
       dari blok pembahasan yang sama (propagasi jangkar paragraf).
    """
    def _find_table_by_id(tid: Optional[str], max_page_dist: int = 3) -> Optional[Dict]:
        if not tid:
            return None
        tid_s = str(tid).strip()
        for t in all_tables:
            if str(t.get("table_id") or "") == tid_s or str(t.get("normalized_id") or "") == tid_s:
                if abs(int(t.get("page", 0)) - claim_page) <= max_page_dist:
                    return t
        return None

    # 1. Cari local_table
    local_table = _find_table_by_id(scope_table_id, max_page_dist=2)

    if not local_table:
        same_page_tables = []
        for t in all_tables:
            if t.get("page") == claim_page:
                y_bot = t.get("y_bottom") or (t.get("bbox", [0, 0, 0, 0])[3] if len(t.get("bbox", [])) >= 4 else 0.0)
                y_top = t.get("bbox", [0, 0, 0, 0])[1] if len(t.get("bbox", [])) >= 4 else 0.0
                if y_bot <= claim_y_top + 25.0 or y_top <= claim_y_top + 10.0:
                    dist = abs(claim_y_top - y_bot)
                    same_page_tables.append((dist, t))

        if same_page_tables:
            same_page_tables.sort(key=lambda item: item[0])
            local_table = same_page_tables[0][1]
        elif claim_page > 1 and claim_y_top <= 250.0:
            prev_page_tables = [t for t in all_tables if t.get("page") == (claim_page - 1)]
            if prev_page_tables:
                prev_page_tables.sort(
                    key=lambda t: float(t.get("bbox", [0, 0, 0, 0])[1] if len(t.get("bbox", [])) >= 4 else 0.0)
                )
                local_table = prev_page_tables[-1]

    # 2. Cari explicit_id dan explicit_table (termasuk cross-page floating table pada page+1 / page-1)
    explicit_id = normalize_table_id(sentence)
    explicit_table = None
    if explicit_id:
        candidates = []
        for t in all_tables:
            t_norm = t.get("normalized_id")
            t_norm_canon = normalize_table_id(str(t_norm)) if t_norm else None
            t_num = str(t.get("table_num", "")).strip()
            t_id = t.get("table_id", "")
            t_cap = str(t.get("caption", ""))
            if (
                t_norm == explicit_id
                or t_norm_canon == explicit_id
                or t_num == explicit_id
                or normalize_table_id(t_id) == explicit_id
                or (t_cap and normalize_table_id(t_cap) == explicit_id)
            ):
                candidates.append(t)
        if candidates:
            # Prefer same page, then floating page+1 / page-1, then nearest page
            candidates.sort(key=lambda t: (abs(int(t.get("page", 0)) - claim_page), 0 if int(t.get("page", 0)) >= claim_page else 1))
            explicit_table = candidates[0]

    # Cek apakah kalimat merupakan kalimat pengantar tabel di bawahnya
    s_low = sentence.lower()
    forward_intro_phrases = (
        "sebagai berikut",
        "berikut ini",
        "di bawah ini",
        "dibawah ini",
        "pada tabel berikut",
    )
    intro_phrases = forward_intro_phrases + (
        "dapat dilihat pada",
        "disajikan pada",
        "disajikan dalam",
        "terlihat pada",
    )
    if any(p in s_low for p in intro_phrases):
        if explicit_table:
            return explicit_table, None
        if any(p in s_low for p in forward_intro_phrases) and next_table_id:
            below_tbl = _find_table_by_id(next_table_id, max_page_dist=1)
            if below_tbl:
                return below_tbl, None
        return local_table or _find_table_by_id(active_discussion_table_id, max_page_dist=3), None

    # 3 & 4. Periksa kecocokan pasangan (kategori/sel, nilai) jika explicit_table dan local_table BERBEDA
    if explicit_table and local_table and (explicit_table.get("table_id") != local_table.get("table_id")):
        # Bersihkan catatan kaki sumber & tahun sebelum mengekstrak angka kalimat
        clean_sent = re.sub(r"\(\s*(?:Sumber|Source)\s*[:\-][^)]*\)", " ", sentence, flags=re.IGNORECASE)

        def _count_likert_pair_matches(tbl: Dict) -> Optional[int]:
            hdrs = list(tbl.get("header_paths", []))
            raw_rows = [
                [str(c.get("raw_val") if isinstance(c, dict) and c.get("raw_val") is not None else ("" if isinstance(c, dict) else c)) for c in r]
                for r in tbl.get("rows", []) if isinstance(r, list)
            ]
            if not is_spss_frequency_table(hdrs, raw_rows):
                return None
            parsed_tbl = parse_spss_frequency_table(hdrs, raw_rows)
            if not parsed_tbl:
                return None
            l_claims = extract_likert_claims_by_clause(clean_sent)
            if not l_claims:
                return None
            matched = 0
            for lc in l_claims:
                row_obj = parsed_tbl.get(lc.category_code)
                if not row_obj:
                    continue
                exp_v = row_obj.cells.get(lc.metric_type)
                if exp_v is not None and abs(lc.claimed_value - exp_v) < 0.05:
                    matched += 1
            return matched

        lik_local = _count_likert_pair_matches(local_table)
        lik_explicit = _count_likert_pair_matches(explicit_table)

        if lik_local is not None and lik_explicit is not None:
            local_matches = lik_local
            explicit_matches = lik_explicit
        else:
            raw_tokens = re.findall(r"(?:^|\s|\()([+-]?(?:\d+[,.]\d+|\d+|[,.]\d+))%?(?:\s|\)|$|[.,;:])", clean_sent)
            sentence_numbers = []
            for tok in raw_tokens:
                c = tok.strip().replace("%", "")
                c = re.sub(r"^([+-]?)[,.](\d+)$", r"\g<1>0.\g<2>", c).replace(",", ".")
                try:
                    fv = float(c)
                    # Abaikan tahun 1900..2099 agar tidak menipu penghitung kecocokan tabel
                    if 1900 <= fv <= 2099 and fv.is_integer():
                        continue
                    sentence_numbers.append(fv)
                except ValueError:
                    pass

            def _count_matches(tbl: Dict) -> int:
                tbl_nums = set()
                for r in tbl.get("rows", []):
                    for cell in r:
                        if isinstance(cell, dict):
                            hp = str(cell.get("header_path") or "").lower()
                            if "cumulative" in hp or "kumulatif" in hp:
                                continue
                            nv = cell.get("num_val")
                            if nv is not None:
                                try:
                                    tbl_nums.add(round(float(nv), 4))
                                except Exception:
                                    pass
                            raw = cell.get("raw_val") or cell.get("text")
                            if raw is not None:
                                try:
                                    rc = str(raw).strip().replace("%", "")
                                    rc = re.sub(r"^([+-]?)[,.](\d+)$", r"\g<1>0.\g<2>", rc).replace(",", ".")
                                    tbl_nums.add(round(float(rc), 4))
                                except Exception:
                                    pass
                        elif isinstance(cell, (int, float)):
                            tbl_nums.add(round(float(cell), 4))
                        elif isinstance(cell, str):
                            try:
                                rc = cell.strip().replace("%", "")
                                rc = re.sub(r"^([+-]?)[,.](\d+)$", r"\g<1>0.\g<2>", rc).replace(",", ".")
                                tbl_nums.add(round(float(rc), 4))
                            except Exception:
                                pass
                cnt = 0
                for sn in sentence_numbers:
                    if any(abs(sn - tn) < 0.02 for tn in tbl_nums):
                        cnt += 1
                return cnt

            local_matches = _count_matches(local_table)
            explicit_matches = _count_matches(explicit_table)

        if local_matches > explicit_matches and local_matches >= 2:
            chosen_table = local_table
            ref_typo_info = {
                "cited_id": explicit_id,
                "actual_id": local_table.get("normalized_id") or local_table.get("table_id"),
                "actual_table": local_table
            }
            return chosen_table, ref_typo_info

    # 5. Jika tidak ada bukti salah ketik
    if explicit_table:
        chosen_table = explicit_table
    elif explicit_id and not explicit_table:
        chosen_table = None
    elif local_table:
        chosen_table = local_table
    else:
        chosen_table = _find_table_by_id(active_discussion_table_id, max_page_dist=3)

    return chosen_table, None


@dataclass
class CleanedSPSSRow:
    row_code: str
    raw_label: str
    cells: Dict[str, float]
    raw_cells: Dict[str, str]


def is_spss_frequency_table(headers: List[str], rows: List[List[str]]) -> bool:
    """Mendeteksi apakah tabel merupakan tabel distribusi frekuensi SPSS (memiliki kolom Frequency/Percent)."""
    if not headers or not rows:
        return False

    hl = [str(h).lower().strip() for h in headers]

    # 1. Kembalikan False jika header mengandung kolom rata-rata/statistik kontinu ATAU tabel demografi responden
    has_continuous_or_demo = any(
        re.search(
            r"\b(?:mean|rata[\s\-]+rata|rerata|std|deviasi|grand\s+mean|"
            r"usia|umur|jenis\s+kelamin|gender|pendidikan|lama\s+bekerja|masa\s+kerja|"
            r"jabatan|pekerjaan|penghasilan|pendapatan|jurusan|fakultas|program\s+studi)\b",
            h,
        )
        for h in hl
    )
    if has_continuous_or_demo:
        return False

    # 2. Kembalikan False jika header itu sendiri berisi >= 2 kategori skala Likert (Matrix Horizontal)
    likert_header_count = 0
    for h in hl:
        if h in ("sts", "ts", "n", "s", "ss", "ks", "rr", "1", "2", "3", "4", "5") or any(
            cat in h for cat in (
                "sangat setuju",
                "tidak setuju",
                "sangat tidak setuju",
                "kurang setuju",
                "netral",
                "ragu",
                "cukup setuju",
                "sangat puas",
                "tidak puas",
                "sangat tidak puas",
                "sangat baik",
                "tidak baik",
                "sangat tidak baik",
            )
        ):
            likert_header_count += 1
    if likert_header_count >= 2:
        return False

    # 3. Cek keberadaan kolom Frekuensi dan/atau Persentase
    has_freq = any("frequency" in h or "frekuensi" in h or h in ("f", "jumlah") for h in hl)
    has_pct = any("percent" in h or "persentase" in h or "%" in h for h in hl)
    if not (has_freq or has_pct):
        return False

    # 4. Wajibkan minimal >= 2 baris data di kolom kiri (rows) benar-benar berupa label kategori Likert (LIKERT_ROW_ALIASES),
    # bukan nama item seperti X1.1 atau X2.1.
    valid_likert_aliases = set()
    for code, aliases in LIKERT_ROW_ALIASES.items():
        if code != "TOTAL":
            for a in aliases:
                valid_likert_aliases.add(a.lower().strip())

    likert_rows_count = 0
    for r in rows:
        if not r:
            continue
        # Abaikan jika kolom label (bukan kolom numerik persentase) mengandung kode item seperti X1.1, X2.1, Item 1
        label_cells_to_check = [r[0]]
        if len(r) > 1 and str(r[0]).strip().lower() in ("", "valid", "missing"):
            label_cells_to_check.append(r[1])
        has_item_code = any(
            re.search(r"\b(?:[a-zA-Z]{1,3}\d+(?:[.,]\d+)+|item\s*\d+|indikator\s*\d+|pernyataan\s*\d+)\b", str(c).lower())
            for c in label_cells_to_check
        )
        is_long_statement = any(len(str(c).strip().split()) >= 4 for c in label_cells_to_check)
        if has_item_code or is_long_statement:
            continue

        row_has_likert = False
        for cell in r[:3]:
            c_low = str(cell).strip().lower()
            if not c_low or c_low in ("valid", "missing"):
                continue
            if c_low in valid_likert_aliases:
                row_has_likert = True
                break
            elif any(c_low.startswith(a) for a in valid_likert_aliases if len(a) >= 4):
                row_has_likert = True
                break
        if row_has_likert:
            likert_rows_count += 1

    min_required = 1 if len(rows) == 1 else 2
    return likert_rows_count >= min_required


def parse_spss_frequency_table(headers: List[str], rows: List[List[str]]) -> Dict[str, CleanedSPSSRow]:
    """
    Memperbaiki bug kolom pertama 'Valid' pada tabel frekuensi SPSS dan shifted columns.
    Menggunakan Right-Aligned Numeric Column Binding: 4 kolom numerik dari kanan ke kiri
    (Cumulative Percent, Valid Percent, Percent, Frequency).
    """
    col_map: Dict[int, str] = {}
    for idx, h in enumerate(headers):
        hl = h.lower().strip()
        if "cumulative" in hl or "kumulatif" in hl:
            col_map[idx] = "CUMULATIVE_PERCENT"
        elif "valid percent" in hl or "persen valid" in hl:
            col_map[idx] = "VALID_PERCENT"
        elif "percent" in hl or "persentase" in hl or "%" in hl:
            col_map[idx] = "PERCENT"
        elif "frequency" in hl or hl in ("frekuensi", "f", "jumlah"):
            col_map[idx] = "FREQUENCY"

    cleaned_rows: Dict[str, CleanedSPSSRow] = {}

    for r in rows:
        if not r:
            continue

        # Extract numeric cells and non-numeric cells
        numeric_cells = []
        non_numeric_cells = []
        for c_idx, cell in enumerate(r):
            c_str = str(cell).strip() if cell is not None else ""
            if not c_str:
                continue
            num_clean = c_str.replace(",", ".")
            if num_clean.startswith(".") or num_clean.startswith("-,") or num_clean.startswith("-."):
                if num_clean.startswith("-"):
                    num_clean = "-0." + num_clean[2:] if num_clean.startswith("-,") else "-0" + num_clean[1:]
                else:
                    num_clean = "0" + num_clean
            try:
                val = float(num_clean)
                numeric_cells.append((c_idx, c_str, val))
            except ValueError:
                non_numeric_cells.append((c_idx, c_str))

        # Determine row label: non-numeric cell that is NOT "valid", "missing", "system", or "cumulative"
        raw_label = ""
        ignored_stub_labels = ("valid", "missing", "system", "cumulative", "cumulative percent")
        for _, cell_text in non_numeric_cells:
            t_low = cell_text.lower().strip()
            if t_low not in ignored_stub_labels:
                raw_label = cell_text.strip()
                break

        # Fallback for label if all cells were numeric or empty (e.g. Likert code "1", "2")
        if not raw_label:
            if non_numeric_cells:
                cand_lbl = non_numeric_cells[0][1].strip()
                if cand_lbl.lower() not in ignored_stub_labels:
                    raw_label = cand_lbl
            elif numeric_cells and len(numeric_cells) > 4:
                # First numeric cell could be the label (e.g. 1, 2, 3, 4, 5)
                raw_label = str(int(numeric_cells[0][2]))
                numeric_cells = numeric_cells[1:]

        if not raw_label or raw_label.lower() in ignored_stub_labels:
            continue

        label_lower = raw_label.lower().strip()
        canonical_code = raw_label.upper()
        for code, aliases in LIKERT_ROW_ALIASES.items():
            if label_lower in aliases or any(label_lower == a for a in aliases):
                canonical_code = code
                break

        cells_val: Dict[str, float] = {}
        cells_raw: Dict[str, str] = {}

        # Prefer exact header-indexed binding when row columns align with mapped headers
        # so Cumulative Percent can NEVER hijack Percent/Valid Percent even when values are identical.
        if col_map and len(r) == len(headers):
            for c_idx, c_str, val in numeric_cells:
                mapped_role = col_map.get(c_idx)
                if mapped_role and mapped_role not in cells_val:
                    cells_val[mapped_role] = val
                    cells_raw[mapped_role] = c_str

        # Fallback: Right-Aligned Numeric Column Binding when columns are shifted (e.g. merged 'Valid' stub)
        if not cells_val or ("FREQUENCY" not in cells_val and "PERCENT" not in cells_val):
            cells_val = {}
            cells_raw = {}
            num_k = len(numeric_cells)
            if num_k >= 4:
                cum_cell = numeric_cells[-1]
                val_pct_cell = numeric_cells[-2]
                pct_cell = numeric_cells[-3]
                freq_cell = numeric_cells[-4]

                cells_val["CUMULATIVE_PERCENT"] = cum_cell[2]
                cells_raw["CUMULATIVE_PERCENT"] = cum_cell[1]

                cells_val["VALID_PERCENT"] = val_pct_cell[2]
                cells_raw["VALID_PERCENT"] = val_pct_cell[1]

                cells_val["PERCENT"] = pct_cell[2]
                cells_raw["PERCENT"] = pct_cell[1]

                cells_val["FREQUENCY"] = freq_cell[2]
                cells_raw["FREQUENCY"] = freq_cell[1]
            elif num_k == 3:
                # Often Total row: Frequency, Percent, Valid Percent (no cumulative)
                val_pct_cell = numeric_cells[-1]
                pct_cell = numeric_cells[-2]
                freq_cell = numeric_cells[-3]

                cells_val["VALID_PERCENT"] = val_pct_cell[2]
                cells_raw["VALID_PERCENT"] = val_pct_cell[1]

                cells_val["PERCENT"] = pct_cell[2]
                cells_raw["PERCENT"] = pct_cell[1]

                cells_val["FREQUENCY"] = freq_cell[2]
                cells_raw["FREQUENCY"] = freq_cell[1]
            elif num_k == 2:
                # Frequency, Percent
                pct_cell = numeric_cells[-1]
                freq_cell = numeric_cells[-2]

                cells_val["PERCENT"] = pct_cell[2]
                cells_raw["PERCENT"] = pct_cell[1]

                cells_val["FREQUENCY"] = freq_cell[2]
                cells_raw["FREQUENCY"] = freq_cell[1]
            elif num_k == 1:
                cells_val["FREQUENCY"] = numeric_cells[0][2]
                cells_raw["FREQUENCY"] = numeric_cells[0][1]

        if cells_val:
            # Never let a later appended/stray duplicate row overwrite an already parsed category
            if canonical_code not in cleaned_rows:
                cleaned_rows[canonical_code] = CleanedSPSSRow(
                    row_code=canonical_code,
                    raw_label=raw_label,
                    cells=cells_val,
                    raw_cells=cells_raw,
                )
            # Stop after closing TOTAL row once at least one category has been parsed
            if canonical_code == "TOTAL" and len(cleaned_rows) >= 2:
                break

    return cleaned_rows


@dataclass
class LikertClauseClaim:
    clause_text: str
    likert_code: str
    stat_column: str
    claimed_value: float
    claimed_decimals: int
    raw_token: str

    @property
    def category_code(self) -> str:
        return self.likert_code

    @property
    def metric_type(self) -> str:
        return self.stat_column

    @property
    def numeric_val(self) -> float:
        return self.claimed_value

    @property
    def raw_str(self) -> str:
        return self.raw_token


def extract_likert_claims_by_clause(sentence: str) -> List[LikertClauseClaim]:
    """
    Memecah kalimat panjang Bab IV menjadi sub-klausa berdasarkan koma, titik-koma, 'dan', 'serta', 'sedangkan'
    sehingga angka di sebelah KIRI ('48 responden atau (48%)', '12 (12%)') terikat akurat
    ke kategori Likert di sebelah KANAN ('menyatakan setuju' -> 'S').
    """
    raw_clauses = re.split(r"[,;]|\b(?:dan|serta|sedangkan)\b", sentence, flags=re.IGNORECASE)
    claims: List[LikertClauseClaim] = []

    for clause in raw_clauses:
        c_clean = clause.strip()
        if not c_clean:
            continue
        c_lower = c_clean.lower()

        matched_code: Optional[str] = None
        for code, patterns in LIKERT_TEXT_TO_CODE:
            if any(re.search(p, c_lower) for p in patterns):
                matched_code = code
                break

        if not matched_code:
            continue

        # Format 1: Format '12 (12%)' atau 'sebanyak 12 (12%)'
        direct_paren = re.search(r"\b(?:sebanyak\s+)?(\d+(?:[.,]\d+)?)\s*(?:responden|orang|siswa|perusahaan|subjek)?\s*\(\s*(\d+(?:[.,]\d+)?)\s*%\s*\)", c_clean, re.I)
        if direct_paren:
            raw_f = direct_paren.group(1)
            val_f = float(raw_f.replace(",", "."))
            dec_f = len(raw_f.split(",")[1]) if "," in raw_f else (len(raw_f.split(".")[1]) if "." in raw_f else 0)
            claims.append(
                LikertClauseClaim(
                    clause_text=c_clean,
                    likert_code=matched_code,
                    stat_column="FREQUENCY",
                    claimed_value=val_f,
                    claimed_decimals=dec_f,
                    raw_token=f"{raw_f} responden",
                )
            )
            raw_p = direct_paren.group(2)
            val_p = float(raw_p.replace(",", "."))
            dec_p = len(raw_p.split(",")[1]) if "," in raw_p else (len(raw_p.split(".")[1]) if "." in raw_p else 0)
            claims.append(
                LikertClauseClaim(
                    clause_text=c_clean,
                    likert_code=matched_code,
                    stat_column="PERCENT",
                    claimed_value=val_p,
                    claimed_decimals=dec_p,
                    raw_token=f"{raw_p}%",
                )
            )
        else:
            for m_freq in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s+(?:responden|orang|siswa|perusahaan|subjek)\b", c_clean, re.I):
                raw_f = m_freq.group(1)
                val_f = float(raw_f.replace(",", "."))
                dec_f = len(raw_f.split(",")[1]) if "," in raw_f else (len(raw_f.split(".")[1]) if "." in raw_f else 0)
                claims.append(
                    LikertClauseClaim(
                        clause_text=c_clean,
                        likert_code=matched_code,
                        stat_column="FREQUENCY",
                        claimed_value=val_f,
                        claimed_decimals=dec_f,
                        raw_token=f"{raw_f} responden",
                    )
                )

            for m_pct in re.finditer(r"(\d+(?:[.,]\d+)?)\s*%", c_clean):
                raw_p = m_pct.group(1)
                val_p = float(raw_p.replace(",", "."))
                dec_p = len(raw_p.split(",")[1]) if "," in raw_p else (len(raw_p.split(".")[1]) if "." in raw_p else 0)
                claims.append(
                    LikertClauseClaim(
                        clause_text=c_clean,
                        likert_code=matched_code,
                        stat_column="PERCENT",
                        claimed_value=val_p,
                        claimed_decimals=dec_p,
                        raw_token=f"{raw_p}%",
                    )
                )

    return claims


def check_likert_row_sum_in_sentence(
    sentence: str,
    table_cleaned: Dict[str, CleanedSPSSRow]
) -> Optional[Dict[str, Any]]:
    """
    Memeriksa penjumlahan responden yang disebut di kalimat paragraf.
    Hanya terbitkan ROW_SUM_MISMATCH jika:
    1. Jumlah narasi MELEBIHI total sampel tabel (claimed_sum > table_total), ATAU
    2. Semua kategori yang aktif di tabel (frekuensi > 0) ikut disebut di kalimat namun totalnya tidak cocok.
    Jangan menuduh kurang jika penulis sengaja hanya menyebut 2-3 kategori Likert mayoritas dalam kalimat ringkas!
    """
    # Cari semua klaim frekuensi di kalimat
    claims = extract_likert_claims_by_clause(sentence)
    freq_claims = [c for c in claims if c.stat_column == "FREQUENCY" and c.likert_code != "TOTAL"]

    distinct_codes = {c.likert_code for c in freq_claims}
    if len(distinct_codes) < 2:
        return None

    if "TOTAL" not in table_cleaned:
        return None

    table_total = table_cleaned["TOTAL"].cells.get("FREQUENCY")
    if table_total is None or table_total <= 0:
        return None

    # Tolak pengecekan jika table_total bukan bilangan bulat positif atau < 5
    # agar nilai Mean/Skor seperti 11.61 tidak pernah dianggap jumlah responden N
    if abs(table_total - round(table_total)) > 1e-3 or table_total < 5:
        return None

    claimed_sum = sum(c.claimed_value for c in freq_claims)

    # Identifikasi kategori aktif pada tabel (yang memiliki frekuensi > 0 dan bukan TOTAL)
    active_table_categories = {
        code for code, row in table_cleaned.items()
        if code != "TOTAL" and row.cells.get("FREQUENCY", 0) > 0
    }

    # Kondisi 1: claimed_sum melebihi table_total (pasti kontradiksi matematis)
    is_exceeded = claimed_sum > (table_total + 0.001)

    # Kondisi 2: Semua kategori tabel disebut tapi jumlahnya tidak sama dengan table_total
    all_categories_mentioned = active_table_categories.issubset(distinct_codes)
    is_all_mentioned_mismatch = all_categories_mentioned and abs(claimed_sum - table_total) > 0.001

    if is_exceeded or is_all_mentioned_mismatch:
        terms = [str(int(c.claimed_value) if c.claimed_value.is_integer() else c.claimed_value) for c in freq_claims]
        sum_str = str(int(claimed_sum) if claimed_sum.is_integer() else claimed_sum)
        tbl_str = str(int(table_total) if table_total.is_integer() else table_total)
        formula_breakdown = " + ".join(terms) + f" = {sum_str} responden"
        relation = "melebihi" if claimed_sum > table_total else "kurang dari"

        return {
            "verdict": "ROW_SUM_MISMATCH",
            "severity": "HIGH",
            "claimed_sum": claimed_sum,
            "table_total": table_total,
            "formula_breakdown": formula_breakdown,
            "explanation": (
                f"PENJUMLAHAN RESPONDEN TIDAK SESUAI: Total responden pada rincian narasi ({sum_str} responden: "
                f"{formula_breakdown}) {relation} total sampel pada tabel rujukan ({tbl_str} responden)."
            )
        }

    return None
