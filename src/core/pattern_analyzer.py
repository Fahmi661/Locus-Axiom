from typing import List, Dict, Any
from collections import Counter

def analyze_error_patterns(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not findings:
        return {"patterns": [], "banner_text": "", "has_patterns": False}
    verdict_counts = Counter()
    col_errors = Counter()
    truncation_count = 0
    for f in findings:
        v = f.get("verdict", "")
        verdict_counts[v] += 1
        dd = f.get("diff_details", {})
        col = dd.get("col_name", "")
        if col:
            col_errors[col] += 1
        if "TRUNCATION" in v or "TRUNCATION_WARNING" == v:
            truncation_count += 1
    patterns = []
    total = len(findings)
    # Truncation pattern
    if truncation_count > 0:
        patterns.append({
            "pattern_type": "SPSS_TRUNCATION",
            "count": truncation_count,
            "message": f"{truncation_count} dari {total} peringatan berasal dari pemotongan desimal SPSS tanpa pembulatan"
        })
    # Column swap pattern
    swap_count = verdict_counts.get("COLUMN_SWAP_ERROR", 0)
    if swap_count > 0:
        common_col = col_errors.most_common(1)[0][0] if col_errors else "kolom"
        patterns.append({
            "pattern_type": "COLUMN_SWAP",
            "count": swap_count,
            "message": f"{swap_count} kali kesalahan pembacaan kolom (kolom paling sering: {common_col})"
        })
    # Value mismatch pattern
    mismatch_count = verdict_counts.get("DIRECT_CELL_CONTRADICTION", 0) + verdict_counts.get("VALUE_MISMATCH", 0)
    if mismatch_count > 0:
        patterns.append({
            "pattern_type": "VALUE_MISMATCH",
            "count": mismatch_count,
            "message": f"{mismatch_count} kali nilai narasi tidak sesuai tabel (kemungkinan salah referensi baris)"
        })
    if patterns:
        banner = " | ".join(p["message"] for p in patterns[:2])
    else:
        banner = ""
    return {
        "patterns": patterns,
        "banner_text": banner,
        "has_patterns": bool(patterns),
        "verdict_distribution": dict(verdict_counts)
    }
