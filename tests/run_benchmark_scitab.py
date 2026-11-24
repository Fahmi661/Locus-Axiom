"""
LOCUS (Scientific Table Verification Engine)
Benchmark Suite for SciTab (EMNLP 2023) Scientific Table Reasoning Dataset
Evaluates CellLinker on real scientific claims across supports, refutes, and not enough info.
100% Offline, CPU-only.
"""

import os
import sys
import json
import time
import re
import argparse
import glob
from typing import Dict, Any, List, Optional, Tuple

# Ensure workspace root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Force offline execution mode
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from backend.layer2_core.cell_linker import CellLinker


def safe_parse_academic_cell(val_str: Any) -> Tuple[Optional[float], int]:
    """Parses a float and decimal places from arbitrary academic table text."""
    if val_str is None:
        return None, 0
    s = str(val_str).strip()
    s = re.sub(r"\[.*?\]", "", s).strip()
    s = s.replace("*", "").replace("%", "").strip()
    s = re.sub(r"^([+-]?)\s*[,.](\d+)$", r"\g<1>0.\g<2>", s)
    m = re.search(r"[+-]?\d+(?:[.,]\d+)?", s)
    if not m:
        return None, 0
    clean_num = m.group(0).replace(",", ".")
    try:
        val = float(clean_num)
        dec = len(clean_num.split(".")[1]) if "." in clean_num else 0
        return val, dec
    except ValueError:
        return None, 0


def build_table_summary_premise(caption: str, headers: List[str], rows_raw: List[List[str]]) -> str:
    """Builds a concise table premise for zero-shot NLI reasoning."""
    parts = []
    if caption:
        parts.append(f"Table: {caption.strip()}")
    if headers:
        clean_hdrs = [h for h in headers if h and not h.startswith("Kolom_")]
        if clean_hdrs:
            parts.append("Columns: " + " | ".join(clean_hdrs[:8]))
    row_strs = []
    for r in rows_raw[:6]:
        if r:
            cleaned_r = [re.sub(r"\[.*?\]", "", str(c)).strip() for c in r[:8]]
            row_strs.append(", ".join(c for c in cleaned_r if c))
    if row_strs:
        parts.append("Data: " + "; ".join(row_strs))
    return " | ".join(parts)[:300]


def load_scitab_entries(dataset_dir: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Loads all SciTab entries from .json and .jsonl files in the specified directory."""
    entries: List[Dict[str, Any]] = []
    json_files = glob.glob(os.path.join(dataset_dir, "*.json"))
    jsonl_files = glob.glob(os.path.join(dataset_dir, "*.jsonl"))
    all_files = sorted(json_files + jsonl_files)

    for f_path in all_files:
        if f_path.endswith(".jsonl"):
            with open(f_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            pass
        else:
            with open(f_path, "r", encoding="utf-8") as f:
                try:
                    content = json.load(f)
                    if isinstance(content, list):
                        entries.extend(content)
                    elif isinstance(content, dict):
                        if "data" in content and isinstance(content["data"], list):
                            entries.extend(content["data"])
                        else:
                            entries.append(content)
                except Exception:
                    pass

    if limit is not None and limit > 0:
        entries = entries[:limit]
    return entries


def convert_scitab_entry(entry: Dict[str, Any], idx: int) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """
    Converts a raw SciTab entry into (tbl, c_obj, gold_label) compatible with CellLinker.
    """
    caption = entry.get("table_caption") or entry.get("table_cpation") or ""
    header_paths = list(entry.get("table_column_names", []))
    content_values = entry.get("table_content_values", [])
    claim_text = entry.get("claim", "")
    gold_label = str(entry.get("label", "not enough info")).strip().lower()

    converted_rows = []
    for r_idx, row_content in enumerate(content_values, 1):
        row_cells = []
        row_label = str(row_content[0]).strip() if row_content else ""
        row_label = re.sub(r"\[.*?\]", "", row_label).strip()

        for c_idx, cell_raw in enumerate(row_content, 1):
            h_path = header_paths[c_idx - 1] if c_idx - 1 < len(header_paths) else f"Kolom_{c_idx}"
            raw_val = re.sub(r"\[.*?\]", "", str(cell_raw)).strip()
            num_val, decimals = safe_parse_academic_cell(cell_raw)

            cell_dict = {
                "row": r_idx,
                "col": c_idx,
                "header_path": h_path,
                "row_label": row_label,
                "raw_val": raw_val,
                "num_val": num_val,
                "decimals": decimals,
                "bbox": [50.0, 100.0 + r_idx * 20.0, 500.0, 120.0 + r_idx * 20.0]
            }
            row_cells.append(cell_dict)
        converted_rows.append(row_cells)

    tbl = {
        "table_id": str(entry.get("table_id") or f"Table_{idx}"),
        "page": 1,
        "caption": caption,
        "header_paths": header_paths,
        "headers": header_paths,
        "rows": converted_rows
    }

    c_obj = {
        "claim_id": str(entry.get("id", idx)),
        "page": 1,
        "text": claim_text,
        "bbox": [72.0, 100.0, 500.0, 120.0]
    }

    return tbl, c_obj, gold_label


def compute_classification_metrics(golds: List[str], preds: List[str], target_classes: List[str]) -> Dict[str, Any]:
    """Computes per-class precision, recall, F1, macro F1, and accuracy."""
    class_stats = {}
    for c in target_classes:
        tp = sum(1 for g, p in zip(golds, preds) if g == c and p == c)
        fp = sum(1 for g, p in zip(golds, preds) if g != c and p == c)
        fn = sum(1 for g, p in zip(golds, preds) if g == c and p != c)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        class_stats[c] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": prec,
            "recall": rec,
            "f1": f1
        }

    macro_f1 = sum(class_stats[c]["f1"] for c in target_classes) / len(target_classes) if target_classes else 0.0
    total_acc = sum(1 for g, p in zip(golds, preds) if g == p) / len(golds) if golds else 0.0

    return {
        "accuracy": total_acc,
        "macro_f1": macro_f1,
        "per_class": class_stats
    }


def run_benchmark():
    parser = argparse.ArgumentParser(description="Run SciTab Benchmark on LOCUS CellLinker")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of evaluation cases")
    parser.add_argument("--data-dir", type=str, default=None, help="Path to SciTab dataset directory")
    args = parser.parse_args()

    dataset_dir = args.data_dir or os.path.join(BASE_DIR, "data", "scitab", "dataset")
    if not os.path.exists(dataset_dir):
        print(f"Error: Folder dataset SciTab tidak ditemukan di '{dataset_dir}'.")
        sys.exit(1)

    print("================================================================================")
    print("LOCUS BENCHMARK EVALUASI DATASET PUBLIK SCITAB (EMNLP 2023)")
    print("Zero-Shot Scientific Table Reasoning | 100% Offline | Zero GPU")
    print("================================================================================")

    entries = load_scitab_entries(dataset_dir, limit=args.limit)
    total_entries = len(entries)
    print(f"Total Sampel SciTab Dimuat : {total_entries}")
    if total_entries == 0:
        print("Dataset kosong. Selesai.")
        return

    print("Menginisialisasi CellLinker Engine...")
    linker = CellLinker()

    golds_3c: List[str] = []
    preds_3c: List[str] = []

    golds_2c: List[str] = []
    preds_2c: List[str] = []

    latencies: List[float] = []
    t_start_all = time.time()

    print("Menjalankan evaluasi inference...\n")
    for idx, entry in enumerate(entries, 1):
        tbl, c_obj, gold_label = convert_scitab_entry(entry, idx)

        t0 = time.time()
        findings = linker.link_claim_to_table(c_obj, [tbl], all_claims=[c_obj])
        lat = (time.time() - t0) * 1000.0
        latencies.append(lat)

        # 3-Class Prediction Logic
        refutes_findings = [f for f in findings if f.get("verdict") not in ("PASS", "PASS_EXACT_MATCH")]
        pass_findings = [f for f in findings if f.get("verdict") in ("PASS", "PASS_EXACT_MATCH")]

        if refutes_findings:
            pred = "refutes"
        elif pass_findings:
            pred = "supports"
        else:
            # Fallback to NLI Engine on concise table representation
            caption = tbl.get("caption", "")
            hdrs = tbl.get("header_paths", [])
            content_vals = entry.get("table_content_values", [])
            premise = build_table_summary_premise(caption, hdrs, content_vals)

            if hasattr(linker, "nli_engine") and linker.nli_engine is not None:
                nli_res = linker.nli_engine.predict_nli(premise, c_obj["text"])
                nli_lbl = nli_res.get("nli_label", "NEUTRAL")
                if nli_lbl == "CONTRADICTION":
                    pred = "refutes"
                elif nli_lbl == "ENTAILMENT":
                    pred = "supports"
                else:
                    pred = "not enough info"
            else:
                pred = "not enough info"

        golds_3c.append(gold_label)
        preds_3c.append(pred)

        # 2-Class evaluation (supports vs refutes pair only)
        if gold_label in ("supports", "refutes"):
            golds_2c.append(gold_label)
            # Binary mapping: if predicted refutes -> refutes, otherwise supports
            preds_2c.append("refutes" if pred == "refutes" else "supports")

        if idx % 100 == 0 or idx == total_entries:
            interim_acc = sum(1 for g, p in zip(golds_3c, preds_3c) if g == p) / len(golds_3c)
            avg_lat_so_far = sum(latencies) / len(latencies)
            print(f"[{idx:4d}/{total_entries}] Akurasi 3-Class Sementara: {interim_acc*100:5.2f}% | Rata-rata Latensi: {avg_lat_so_far:6.2f} ms/klaim")

    total_time = time.time() - t_start_all
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    # Metrics 3-Class
    classes_3c = ["supports", "refutes", "not enough info"]
    m_3c = compute_classification_metrics(golds_3c, preds_3c, classes_3c)

    # Metrics 2-Class (Binary supports vs refutes)
    classes_2c = ["refutes", "supports"]
    m_2c = compute_classification_metrics(golds_2c, preds_2c, classes_2c)
    refutes_stats = m_2c["per_class"]["refutes"]

    print("\n================================================================================")
    print("HASIL BENCHMARK LENGKAP SCITAB (DATASET PUBLIK)")
    print("================================================================================")
    print(f"Total Kasus Dievaluasi  : {total_entries}")
    print(f"Total Waktu Eksekusi    : {total_time:.2f} detik")
    print(f"Rata-rata Latensi CPU   : {avg_lat:.2f} ms / klaim")
    print("--------------------------------------------------------------------------------")
    print("EVALUASI 3-CLASS (supports / refutes / not enough info):")
    print(f"  Akurasi 3-Class       : {m_3c['accuracy'] * 100:.2f}%  (Baseline Zero-Shot LLM SciTab: 38.05%)")
    print(f"  Macro F1-Score        : {m_3c['macro_f1'] * 100:.2f}%")
    for c in classes_3c:
        st = m_3c["per_class"][c]
        print(f"    - {c:16s}: Prec: {st['precision']*100:5.2f}% | Rec: {st['recall']*100:5.2f}% | F1: {st['f1']*100:5.2f}% (TP={st['tp']}, FP={st['fp']}, FN={st['fn']})")
    print("--------------------------------------------------------------------------------")
    print("EVALUASI 2-CLASS (supports vs refutes):")
    print(f"  Total Sampel 2-Class  : {len(golds_2c)}")
    print(f"  Akurasi Pasangan      : {m_2c['accuracy'] * 100:.2f}%")
    print(f"  Deteksi Refutes       : Precision = {refutes_stats['precision']*100:.2f}%")
    print(f"                          Recall    = {refutes_stats['recall']*100:.2f}%")
    print(f"                          F1-Score  = {refutes_stats['f1']*100:.2f}%")
    print("================================================================================")

    # Save results to JSON
    results_out = {
        "dataset": "SciTab (EMNLP 2023)",
        "total_evaluated": total_entries,
        "total_time_seconds": round(total_time, 2),
        "average_latency_ms": round(avg_lat, 2),
        "three_class_evaluation": {
            "accuracy": round(m_3c["accuracy"], 4),
            "macro_f1": round(m_3c["macro_f1"], 4),
            "baseline_scitab_zeroshot_llm": 0.3805,
            "per_class": m_3c["per_class"]
        },
        "two_class_evaluation": {
            "total_pairs": len(golds_2c),
            "accuracy": round(m_2c["accuracy"], 4),
            "refutes_precision": round(refutes_stats["precision"], 4),
            "refutes_recall": round(refutes_stats["recall"], 4),
            "refutes_f1": round(refutes_stats["f1"], 4)
        }
    }

    out_file = os.path.join(BASE_DIR, "data", "scitab_benchmark_results.json")
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(results_out, f, indent=2, ensure_ascii=False)
        print(f"Hasil lengkap berhasil disimpan ke: {out_file}")
    except Exception as e:
        print(f"Peringatan: Gagal menyimpan hasil ke JSON: {e}")


if __name__ == "__main__":
    run_benchmark()
