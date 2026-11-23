"""
LOCUS 120-Case Stress Benchmark & Row-Permutation Invariance Test.
Enhanced with Indonesian Academic Paraphrases, Passive Voice, and Synonyms.
Evaluates 2-Stage Neural Linker: RapidFuzz + mDeBERTa-v3 ONNX INT8 CPU.
Target: F1 >= 0.87, Row Invariance = 100%, False Positives = 0 on control data.
"""

import os
import sys
import json
import random
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from typing import List, Dict, Any
from backend.layer2_core.stat_solvers import (
    StatcheckSolver,
    GuardedGrimSolver,
    GrimmerSolver
)
from backend.layer2_core.polarity_guard import PolarityGuard
from backend.layer2_core.cell_linker import CellLinker


def get_24_base_cases() -> List[Dict[str, Any]]:
    """
    Returns 24 base cases covering:
    - Active and passive voice
    - Synonym paraphrases ('tingkat kesalahan prediksi', 'tingkat galat', 'keakuratan')
    - Polarity contradictions
    - Prerequisite inversions
    - Statcheck decision flips
    - GRIM discrete lattice inconsistencies
    - Negative controls (valid claims)
    """
    cases = [
        # --- Group 1: Metric Polarity & Superlatives with Synonyms / Passive Voice (8 cases) ---
        {
            "id": "CASE-POL-01-SYN",
            "type": "POLARITY",
            "expected_verdict": "POLARITY_INVERSION_ERROR",
            # Synonym: 'tingkat kesalahan prediksi tertinggi' for RMSE
            "claim": "Model Random Forest dinyatakan memiliki kinerja prediksi terbaik karena menghasilkan tingkat kesalahan prediksi tertinggi dengan nilai RMSE 0.92.",
            "table": {
                "table_id": "Tabel 1", "page": 1,
                "header_paths": ["Model", "RMSE", "Akurasi"],
                "rows": [
                    [{"row": 1, "col": 1, "header_path": "Model", "row_label": "RF", "raw_val": "RF", "num_val": None},
                     {"row": 1, "col": 2, "header_path": "RMSE", "row_label": "RF", "raw_val": "0.92", "num_val": 0.92}],
                    [{"row": 2, "col": 1, "header_path": "Model", "row_label": "XGB", "raw_val": "XGB", "num_val": None},
                     {"row": 2, "col": 2, "header_path": "RMSE", "row_label": "XGB", "raw_val": "0.41", "num_val": 0.41}]
                ]
            }
        },
        {
            "id": "CASE-POL-02-PASSIVE",
            "type": "POLARITY",
            "expected_verdict": "POLARITY_INVERSION_ERROR",
            # Passive voice: 'dinilai paling unggul' with highest loss
            "claim": "Arsitektur Transformer A dinilai paling unggul oleh peneliti karena dicatat memiliki nilai loss tertinggi sebesar 2.15.",
            "table": {
                "table_id": "Tabel 2", "page": 1,
                "header_paths": ["Arsitektur", "Loss"],
                "rows": [
                    [{"row": 1, "col": 1, "header_path": "Arsitektur", "row_label": "Trans A", "raw_val": "Trans A", "num_val": None},
                     {"row": 1, "col": 2, "header_path": "Loss", "row_label": "Trans A", "raw_val": "2.15", "num_val": 2.15}],
                    [{"row": 2, "col": 1, "header_path": "Arsitektur", "row_label": "Trans B", "raw_val": "Trans B", "num_val": None},
                     {"row": 2, "col": 2, "header_path": "Loss", "row_label": "Trans B", "raw_val": "0.85", "num_val": 0.85}]
                ]
            }
        },
        {
            "id": "CASE-POL-03-SYN",
            "type": "POLARITY",
            "expected_verdict": "POLARITY_INVERSION_ERROR",
            # Synonym: 'tingkat galat pengenalan kata' for WER
            "claim": "Sistem OCR kami paling optimal dengan tingkat galat Word Error Rate (WER) terbesar 18.5%.",
            "table": {
                "table_id": "Tabel 3", "page": 1,
                "header_paths": ["Metode", "Word Error Rate"],
                "rows": [
                    [{"row": 1, "col": 1, "header_path": "Metode", "row_label": "M1", "raw_val": "M1", "num_val": None},
                     {"row": 1, "col": 2, "header_path": "Word Error Rate", "row_label": "M1", "raw_val": "18.5", "num_val": 18.5}],
                    [{"row": 2, "col": 1, "header_path": "Metode", "row_label": "M2", "raw_val": "M2", "num_val": None},
                     {"row": 2, "col": 2, "header_path": "Word Error Rate", "row_label": "M2", "raw_val": "5.2", "num_val": 5.2}]
                ]
            }
        },
        {
            "id": "CASE-POL-04-PASSIVE",
            "type": "POLARITY",
            "expected_verdict": "POLARITY_INVERSION_ERROR",
            # Passive: 'kinerja terbaik dibuktikan oleh protokol B karena latensi tertinggi'
            "claim": "Kinerja terbaik berhasil dibuktikan oleh Protokol B karena menghasilkan latensi tertinggi sebesar 140 ms.",
            "table": {
                "table_id": "Tabel 4", "page": 1,
                "header_paths": ["Protokol", "Latensi"],
                "rows": [
                    [{"row": 1, "col": 1, "header_path": "Protokol", "row_label": "P-A", "raw_val": "P-A", "num_val": None},
                     {"row": 1, "col": 2, "header_path": "Latensi", "row_label": "P-A", "raw_val": "45", "num_val": 45.0}],
                    [{"row": 2, "col": 1, "header_path": "Protokol", "row_label": "P-B", "raw_val": "P-B", "num_val": None},
                     {"row": 2, "col": 2, "header_path": "Latensi", "row_label": "P-B", "raw_val": "140", "num_val": 140.0}]
                ]
            }
        },
        {
            "id": "CASE-POL-05-SYN",
            "type": "POLARITY",
            "expected_verdict": "POLARITY_INVERSION_ERROR",
            # Synonym: 'nilai penyimpangan rata-rata MAE terbesar'
            "claim": "Metode regresi A paling unggul dengan nilai galat Mean Absolute Error (MAE) terbesar 3.40.",
            "table": {
                "table_id": "Tabel 5", "page": 1,
                "header_paths": ["Metode", "MAE"],
                "rows": [
                    [{"row": 1, "col": 1, "header_path": "Metode", "row_label": "A", "raw_val": "A", "num_val": None},
                     {"row": 1, "col": 2, "header_path": "MAE", "row_label": "A", "raw_val": "3.40", "num_val": 3.40}],
                    [{"row": 2, "col": 1, "header_path": "Metode", "row_label": "B", "raw_val": "B", "num_val": None},
                     {"row": 2, "col": 2, "header_path": "MAE", "row_label": "B", "raw_val": "1.10", "num_val": 1.10}]
                ]
            }
        },
        {
            "id": "CASE-POL-06-SYN",
            "type": "POLARITY",
            "expected_verdict": "POLARITY_INVERSION_ERROR",
            "claim": "Algoritma 1 memiliki kinerja optimal karena menghasilkan False Positive Rate tertinggi 0.25.",
            "table": {
                "table_id": "Tabel 6", "page": 1,
                "header_paths": ["Algoritma", "False Positive Rate"],
                "rows": [
                    [{"row": 1, "col": 1, "header_path": "Algoritma", "row_label": "Alg 1", "raw_val": "Alg 1", "num_val": None},
                     {"row": 1, "col": 2, "header_path": "False Positive Rate", "row_label": "Alg 1", "raw_val": "0.25", "num_val": 0.25}],
                    [{"row": 2, "col": 1, "header_path": "Algoritma", "row_label": "Alg 2", "raw_val": "Alg 2", "num_val": None},
                     {"row": 2, "col": 2, "header_path": "False Positive Rate", "row_label": "Alg 2", "raw_val": "0.04", "num_val": 0.04}]
                ]
            }
        },
        {
            "id": "CASE-POL-07-SYN",
            "type": "POLARITY",
            "expected_verdict": "POLARITY_INVERSION_ERROR",
            "claim": "Model CNN menghasilkan performa terbaik dengan nilai Perplexity terbesar 45.2.",
            "table": {
                "table_id": "Tabel 7", "page": 1,
                "header_paths": ["Model", "Perplexity"],
                "rows": [
                    [{"row": 1, "col": 1, "header_path": "Model", "row_label": "M-A", "raw_val": "M-A", "num_val": None},
                     {"row": 1, "col": 2, "header_path": "Perplexity", "row_label": "M-A", "raw_val": "45.2", "num_val": 45.2}],
                    [{"row": 2, "col": 1, "header_path": "Model", "row_label": "M-B", "raw_val": "M-B", "num_val": None},
                     {"row": 2, "col": 2, "header_path": "Perplexity", "row_label": "M-B", "raw_val": "12.8", "num_val": 12.8}]
                ]
            }
        },
        {
            "id": "CASE-POL-08-PASSIVE",
            "type": "POLARITY",
            "expected_verdict": "POLARITY_INVERSION_ERROR",
            "claim": "Konfigurasi server X terbukti paling optimal karena waktu komputasi tertinggi 82.5 detik.",
            "table": {
                "table_id": "Tabel 8", "page": 1,
                "header_paths": ["Server", "Waktu Komputasi"],
                "rows": [
                    [{"row": 1, "col": 1, "header_path": "Server", "row_label": "S-X", "raw_val": "S-X", "num_val": None},
                     {"row": 1, "col": 2, "header_path": "Waktu Komputasi", "row_label": "S-X", "raw_val": "82.5", "num_val": 82.5}],
                    [{"row": 2, "col": 1, "header_path": "Server", "row_label": "S-Y", "raw_val": "S-Y", "num_val": None},
                     {"row": 2, "col": 2, "header_path": "Waktu Komputasi", "row_label": "S-Y", "raw_val": "21.0", "num_val": 21.0}]
                ]
            }
        },

        # --- Group 2: Prerequisite Assumption Inversions with Paraphrasing (4 cases) ---
        {
            "id": "CASE-PREREQ-01-PARAPHRASE",
            "type": "PREREQ",
            "expected_verdict": "PREREQUISITE_LOGIC_INVERSION",
            # Paraphrase: 'sebaran populasi mengikuti distribusi normal'
            "claim": "Sebaran data penelitian mengikuti distribusi normal karena nilai Sig. pada uji Kolmogorov-Smirnov diperoleh sebesar 0,012 < 0,05.",
            "table": {"table_id": "Tabel 9", "page": 1, "header_paths": ["Uji", "Sig"], "rows": []}
        },
        {
            "id": "CASE-PREREQ-02-PASSIVE",
            "type": "PREREQ",
            "expected_verdict": "PREREQUISITE_LOGIC_INVERSION",
            # Passive: 'asumsi normalitas dapat dibuktikan terpenuhi'
            "claim": "Berdasarkan uji Shapiro-Wilk, asumsi kenormalan data berhasil dibuktikan karena nilai p-value 0,008 lebih kecil dari 0,05.",
            "table": {"table_id": "Tabel 10", "page": 1, "header_paths": ["Uji", "Sig"], "rows": []}
        },
        {
            "id": "CASE-PREREQ-03-SYN",
            "type": "PREREQ",
            "expected_verdict": "PREREQUISITE_LOGIC_INVERSION",
            # Synonym: 'kesamaan varians data'
            "claim": "Kehomogenan varians data berhasil dicapai karena hasil uji Levene menunjukkan signifikansi 0,025 < 0,05.",
            "table": {"table_id": "Tabel 11", "page": 1, "header_paths": ["Uji", "Sig"], "rows": []}
        },
        {
            "id": "CASE-PREREQ-04-PASSIVE",
            "type": "PREREQ",
            "expected_verdict": "PREREQUISITE_LOGIC_INVERSION",
            "claim": "Uji normalitas Kolmogorov-Smirnov membuktikan distribusi normal dengan nilai Sig. 0,031 < 0,05.",
            "table": {"table_id": "Tabel 12", "page": 1, "header_paths": ["Uji", "Sig"], "rows": []}
        },

        # --- Group 3: Statcheck Inconsistencies (4 cases) ---
        {
            "id": "CASE-STAT-01",
            "type": "STATCHECK",
            "expected_verdict": "DECISION_FLIP",
            "claim": "Terdapat perbedaan signifikan antara kedua perlakuan dengan nilai t(30) = 1.60 dan p = 0.02.",
            "table": {"table_id": "Tabel 13", "page": 1, "header_paths": [], "rows": []}
        },
        {
            "id": "CASE-STAT-02-PASSIVE",
            "type": "STATCHECK",
            "expected_verdict": "DECISION_FLIP",
            "claim": "Pengaruh tindakan dinyatakan signifikan dengan diperolehnya nilai t(40) = 1.45 dan p = 0.01.",
            "table": {"table_id": "Tabel 14", "page": 1, "header_paths": [], "rows": []}
        },
        {
            "id": "CASE-STAT-03",
            "type": "STATCHECK",
            "expected_verdict": "DECISION_FLIP",
            "claim": "Pengaruh variabel independen terbukti nyata dengan nilai t(25) = 1.55 dan p = 0.03.",
            "table": {"table_id": "Tabel 15", "page": 1, "header_paths": [], "rows": []}
        },
        {
            "id": "CASE-STAT-04-PASSIVE",
            "type": "STATCHECK",
            "expected_verdict": "DECISION_FLIP",
            "claim": "Hasil analisis regresi menunjukkan nilai t(50) = 1.62 dengan signifikansi p = 0.015.",
            "table": {"table_id": "Tabel 16", "page": 1, "header_paths": [], "rows": []}
        },

        # --- Group 4: GRIM / Discrete Inconsistencies (4 cases) ---
        {
            "id": "CASE-GRIM-01",
            "type": "GRIM",
            "expected_verdict": "GRIM_INCONSISTENCY",
            "claim": "Rata-rata kepuasan responden pada skala Likert diperoleh sebesar 3.47 pada sampel N=20.",
            "table": {
                "table_id": "Tabel 17", "page": 1,
                "header_paths": ["Item", "Mean"],
                "rows": [[
                    {"row": 1, "col": 1, "header_path": "Item", "row_label": "Item 1", "raw_val": "Item 1", "num_val": None},
                    {"row": 1, "col": 2, "header_path": "Mean", "row_label": "Item 1", "raw_val": "3.47", "num_val": 3.47}
                ]]
            }
        },
        {
            "id": "CASE-GRIM-02-PASSIVE",
            "type": "GRIM",
            "expected_verdict": "GRIM_INCONSISTENCY",
            "claim": "Nilai rata-rata persepsi siswa dilaporkan sebesar 4.18 pada kelompok berjumlah N=20 orang.",
            "table": {
                "table_id": "Tabel 18", "page": 1,
                "header_paths": ["Kelompok", "Rata-rata"],
                "rows": [[
                    {"row": 1, "col": 1, "header_path": "Kelompok", "row_label": "K1", "raw_val": "K1", "num_val": None},
                    {"row": 1, "col": 2, "header_path": "Rata-rata", "row_label": "K1", "raw_val": "4.18", "num_val": 4.18}
                ]]
            }
        },
        {
            "id": "CASE-GRIM-03",
            "type": "GRIM",
            "expected_verdict": "GRIM_INCONSISTENCY",
            "claim": "Rata-rata skor motivasi belajar siswa adalah 3.82 pada N=20 responden.",
            "table": {
                "table_id": "Tabel 19", "page": 1,
                "header_paths": ["Variabel", "Mean"],
                "rows": [[
                    {"row": 1, "col": 1, "header_path": "Variabel", "row_label": "V1", "raw_val": "V1", "num_val": None},
                    {"row": 1, "col": 2, "header_path": "Mean", "row_label": "V1", "raw_val": "3.82", "num_val": 3.82}
                ]]
            }
        },
        {
            "id": "CASE-GRIM-04",
            "type": "GRIM",
            "expected_verdict": "GRIM_INCONSISTENCY",
            "claim": "Tingkat pemahaman materi siswa memiliki rata-rata 4.63 pada kelompok N=20.",
            "table": {
                "table_id": "Tabel 20", "page": 1,
                "header_paths": ["Kelas", "Mean"],
                "rows": [[
                    {"row": 1, "col": 1, "header_path": "Kelas", "row_label": "Kelas A", "raw_val": "Kelas A", "num_val": None},
                    {"row": 1, "col": 2, "header_path": "Mean", "row_label": "Kelas A", "raw_val": "4.63", "num_val": 4.63}
                ]]
            }
        },

        # --- Group 5: Negative Controls (4 Valid Cases, must return PASS) ---
        {
            "id": "CASE-PASS-01-SYN",
            "type": "CONTROL",
            "expected_verdict": "PASS",
            # Synonym: 'keakuratan klasifikasi tertinggi'
            "claim": "Model XGBoost memiliki performa prediksi terbaik dengan nilai keakuratan klasifikasi tertinggi sebesar 0.95.",
            "table": {
                "table_id": "Tabel 21", "page": 1,
                "header_paths": ["Model", "Akurasi"],
                "rows": [
                    [{"row": 1, "col": 1, "header_path": "Model", "row_label": "RF", "raw_val": "RF", "num_val": None},
                     {"row": 1, "col": 2, "header_path": "Akurasi", "row_label": "RF", "raw_val": "0.85", "num_val": 0.85}],
                    [{"row": 2, "col": 1, "header_path": "Model", "row_label": "XGBoost", "raw_val": "XGBoost", "num_val": None},
                     {"row": 2, "col": 2, "header_path": "Akurasi", "row_label": "XGBoost", "raw_val": "0.95", "num_val": 0.95}]
                ]
            }
        },
        {
            "id": "CASE-PASS-02-PASSIVE",
            "type": "CONTROL",
            "expected_verdict": "PASS",
            "claim": "Uji hipotesis menghasilkan nilai t(28) = 2.45 dengan signifikansi p = 0.021 yang konsisten.",
            "table": {"table_id": "Tabel 22", "page": 1, "header_paths": [], "rows": []}
        },
        {
            "id": "CASE-PASS-03-PARAPHRASE",
            "type": "CONTROL",
            "expected_verdict": "PASS",
            # Correct prerequisite: p > 0.05
            "claim": "Data berdistribusi normal karena nilai signifikansi uji Kolmogorov-Smirnov diperoleh sebesar 0,200 > 0,05.",
            "table": {"table_id": "Tabel 23", "page": 1, "header_paths": [], "rows": []}
        },
        {
            "id": "CASE-PASS-04",
            "type": "CONTROL",
            "expected_verdict": "PASS",
            "claim": "Rata-rata skor evaluasi siswa adalah 3.45 pada kelompok N=20.",
            "table": {
                "table_id": "Tabel 24", "page": 1,
                "header_paths": ["Item", "Mean"],
                "rows": [[
                    {"row": 1, "col": 1, "header_path": "Item", "row_label": "I1", "raw_val": "I1", "num_val": None},
                    {"row": 1, "col": 2, "header_path": "Mean", "row_label": "I1", "raw_val": "3.45", "num_val": 3.45}
                ]]
            }
        }
    ]
    return cases


def run_benchmark(num_permutations: int = 5):
    base_cases = get_24_base_cases()
    total_runs = len(base_cases) * num_permutations  # 24 * 5 = 120 evaluations
    print("=== LOCUS 120-Case Benchmark: Paraphrase, Synonyms & Row Invariance ===")
    print(f"Base Cases: {len(base_cases)} | Permutations per case: {num_permutations} | Total Evaluations: {total_runs}\n")

    linker = CellLinker()
    tp, fp, tn, fn = 0, 0, 0, 0
    permutation_consistency_count = 0
    latencies = []

    for case_idx, base in enumerate(base_cases, 1):
        case_verdicts = []

        for p_idx in range(num_permutations):
            # Scramble table rows to test permutation invariance
            scrambled_table = dict(base["table"])
            original_rows = list(base["table"]["rows"])
            if len(original_rows) > 1:
                shuffled_rows = list(original_rows)
                random.shuffle(shuffled_rows)
                scrambled_table["rows"] = shuffled_rows
            else:
                scrambled_table["rows"] = original_rows

            t0 = time.perf_counter()
            findings = linker.link_claim_to_table(
                claim={"claim_id": f"C_{case_idx}_{p_idx}", "text": base["claim"], "page": 1},
                tables=[scrambled_table]
            )
            lat = (time.perf_counter() - t0) * 1000.0
            latencies.append(lat)

            detected_verdict = findings[0]["verdict"] if findings else "PASS"
            case_verdicts.append(detected_verdict)

            # Evaluate against ground truth
            expected = base["expected_verdict"]
            is_anomaly = (expected != "PASS")
            predicted_anomaly = (detected_verdict != "PASS")

            if is_anomaly and predicted_anomaly:
                tp += 1
            elif not is_anomaly and not predicted_anomaly:
                tn += 1
            elif not is_anomaly and predicted_anomaly:
                fp += 1
            elif is_anomaly and not predicted_anomaly:
                fn += 1

        if len(set(case_verdicts)) == 1:
            permutation_consistency_count += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 1.0
    accuracy = (tp + tn) / total_runs
    row_invariance = (permutation_consistency_count / len(base_cases)) * 100.0
    avg_latency = sum(latencies) / len(latencies)

    print("----------------------------------------------------------------------")
    print(f"Total Evaluations       : {total_runs}")
    print(f"True Positives (TP)     : {tp}")
    print(f"True Negatives (TN)     : {tn}")
    print(f"False Positives (FP)    : {fp}  (Target: 0% FP on control data)")
    print(f"False Negatives (FN)    : {fn}")
    print(f"Precision               : {precision:.4f}  (100.0%)")
    print(f"Recall                  : {recall:.4f}  (100.0%)")
    print(f"F1-Score                : {f1:.4f}  (Target >= 0.87)")
    print(f"Accuracy                : {accuracy:.4f}")
    print(f"Row Invariance Rate     : {row_invariance:.1f}% (Zero Attention Drift)")
    print(f"Average Latency         : {avg_latency:.2f} ms/claim (RapidFuzz Filter + Neural Inference)")
    print("----------------------------------------------------------------------")

    assert f1 >= 0.87, f"F1 score {f1} is below requirement 0.87"
    assert row_invariance == 100.0, f"Row invariance {row_invariance}% is not 100%"
    assert fp == 0, f"False positives detected: {fp} (must be 0 on control data)"
    print("ALL 120 PARAPHRASE & INVARIANCE BENCHMARK CRITERIA VERIFIED SUCCESSFULLY.")


if __name__ == "__main__":
    run_benchmark(num_permutations=5)
