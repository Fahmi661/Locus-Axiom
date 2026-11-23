<div align="center">

# LOCUS

### Cursor for Scientific Integrity

**Audit otomatis konsistensi tabel, narasi, dan statistik skripsi. 100% offline, tanpa GPU.**

![Python](https://img.shields.io/badge/Python-3.10--3.14-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688)
![ONNX](https://img.shields.io/badge/ONNX-INT8%20CPU-orange)
![Offline](https://img.shields.io/badge/mode-100%25%20offline-success)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-pytest-informational)

`/ LO-KUS /` - dikembangkan untuk **Hackvidia Arkavidia 11.0 (HMIF ITB)**, Subtema 4: *Learning & Self-Growth*

[Mulai Cepat](#mulai-cepat) | [Cara Pakai](#cara-pakai) | [Arsitektur](#arsitektur) | [API](#dokumentasi-api) | [Kontribusi](#kontribusi)

</div>

---

<div align="center">

<img src="https://ufxjvugkmiorxlogvcmx.supabase.co/storage/v1/object/public/portfolio-assets/LOCUS_demo.gif" alt="Demo LOCUS X-Ray Studio: audit skripsi dari unggah PDF sampai sertifikat" width="900">

<sub>Demo LOCUS X-Ray Studio: unggah PDF, audit offline, telusuri temuan, ekspor sertifikat.</sub>

</div>

---

## Apa itu LOCUS?

Pemeriksa plagiarisme seperti Turnitin hanya membandingkan kemiripan kata. Mereka **tidak melihat** angka di tabel yang bertentangan dengan kalimat narasi di halaman yang sama. LLM cloud juga bukan solusi: sering salah hitung, boros VRAM, dan mengirim naskah belum terbit ke server pihak ketiga.

LOCUS memakai pendekatan **neuro-simbolik offline**:

| Komponen | Tugas | Teknologi |
| :-- | :-- | :-- |
| **Neural** | Membaca bahasa alami, memecah klausa, menautkan klaim ke baris/kolom tabel yang tepat | ONNX INT8 di CPU |
| **Simbolik** | Memutuskan lolos / peringatan / salah fatal lewat perhitungan eksak | SciPy + NumPy |

Hasil: keputusan validitas dihitung deterministik (bukan ditebak model), dengan target **0% false positive pada dokumen kontrol** dan waktu **< 0,2 ms per klaim** di solver.

**Cocok untuk:** mahasiswa pra-sidang, dosen pembimbing/penguji, reviewer jurnal, dan unit penjaminan mutu kampus.

---

## Fitur Utama

- **Audit tabel vs narasi** - mendeteksi angka paragraf yang tidak cocok dengan tabel bukti.
- **Quad-Tuple Grounding** - setiap klaim diikat ke `Variabel + Statistik + Nilai + Toleransi Pembulatan` sebelum dinilai.
- **8 solver matematika** - Statcheck, GRIM, GRIMMER, DEBIT, Confusion Matrix, Tuple, Formula, Superlative.
- **Spesialisasi SPSS, Likert, EViews** - tabel frekuensi SPSS, skala 5 poin, format desimal Indonesia (`1.450,25`).
- **Polarity Guard** - menangkap salah arah RMSE/MAE dan salah tafsir uji normalitas Kolmogorov-Smirnov.
- **X-Ray Studio** - PDF asli di samping temuan, sorotan klaim dan sel bukti, garis Bezier penghubung.
- **What-If Stepper** - simulasi ubah sel tabel (+-0,01) untuk melihat apakah klaim menjadi valid.
- **Explain-First Scaffolding** - kuis MCQ edukatif sebelum saran revisi.
- **Sertifikat Audit SHA-256** - tanda terima digital dengan PII yang disamarkan.
- **Non-blocking + progress realtime + pembatalan nyata** untuk dokumen 20-60 halaman.

---

## Mulai Cepat

### Prasyarat

| Kebutuhan | Minimum | Disarankan |
| :-- | :-- | :-- |
| OS | Windows 10/11, Ubuntu 20.04+, macOS | - |
| Python | 3.10 | 3.11 atau 3.12 |
| RAM | 8 GB | 16 GB |
| GPU | Tidak perlu | Tidak perlu |
| Disk | ~1,5 GB (model + dependensi) | - |
| Internet | Hanya saat instalasi | - |

### 1. Clone repositori

```bash
git clone https://github.com/<username>/locus.git
cd locus
```

### 2. Buat virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Pasang dependensi

```bash
pip install -r requirements.txt
```

### 4. Siapkan model ONNX INT8

Model berukuran besar (~840 MB total) sehingga **tidak disimpan langsung di Git**. Unduh dari halaman **Releases** repositori ini (atau tautan yang disediakan maintainer), lalu ekstrak ke `data/models/` dengan susunan berikut:

```text
data/models/
├── bge-reranker-v2-m3/
│   ├── onnx/model_int8.onnx        # ~570 MB
│   └── tokenizer.json
└── onnx/
    ├── model_quantized.onnx        # ~270 MB
    └── tokenizer.json
```

> Verifikasi: kedua file `.onnx` dan kedua `tokenizer.json` harus ada sebelum server dijalankan.

### 5. Jalankan server

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### 6. Buka di browser

| Halaman | URL |
| :-- | :-- |
| LOCUS Studio | http://127.0.0.1:8000/app/studio.html |
| Landing page | http://127.0.0.1:8000/app/index.html |
| Swagger API | http://127.0.0.1:8000/docs |

Pengguna Windows juga dapat memakai peluncur desktop:

```bash
python desktop_launcher.py
```

---

## Cara Pakai

1. Buka **LOCUS Studio**, lalu seret berkas PDF skripsi (disarankan Bab 4 atau Hasil dan Pembahasan) ke dropzone.
2. Pantau progres audit (halaman ke-N, klaim ke-N). Klik **Batalkan** kapan saja jika perlu.
3. Telusuri temuan di panel kiri. Filter: **Semua / Fatal / Peringatan / Lolos**.
4. Klik satu temuan untuk melihat:
   - sorotan klaim di teks dan sel bukti di tabel,
   - perbandingan **Tertulis vs Tabel vs Delta**,
   - penjelasan dan saran redaksi revisi.
5. Coba **What-If Stepper** untuk menguji sensitivitas angka.
6. Ekspor **Sertifikat Audit SHA-256** untuk dilampirkan saat bimbingan atau revisi sidang.

### Tingkat keparahan temuan

| Status | Warna | Arti |
| :-- | :-- | :-- |
| `fatal` | Merah | Angka/logika salah secara matematis atau kesimpulan terbalik |
| `warning` | Kuning | Selisih pembulatan, pemotongan desimal, atau ketidakkonsistenan ringan |
| `pass` | Hijau | Klaim konsisten dengan tabel |

> LOCUS adalah **alat bantu audit**, bukan pengganti penilaian dosen. Selalu periksa temuan secara manual sebelum merevisi.

---

## Arsitektur

Tiga lapisan independen dengan kontrak data yang ketat:

```text
                     Naskah PDF Skripsi
                            |
                            v
 LAPISAN 1: PERSEPSI & GEOMETRI  (backend/layer1_perception)
   - FastPdfReader (pypdfium2) + table-masking text extractor
   - TableGeometryExtractor: tabel 3-garis standar skripsi
                            |
                            v
 LAPISAN 2: CORE NEURO-SIMBOLIK  (backend/layer2_core)
   2A  Pemisah klausa kontrastif + stemmer alias variabel
   2B  Reranker (BGE) + NLI (mDeBERTa), ONNX INT8 di CPU
   2C  Suite 8 solver deterministik
   2D  Abstention Gate + Polarity Guard
                            |
                            v
 LAPISAN 3: STUDIO & SERTIFIKAT  (frontend + backend/layer3_export)
   - Dual-pane viewer, overlay per halaman, kurva Bezier
   - What-If stepper, Explain-First MCQ
   - PII redactor + SHA-256 receipt
```

### Format Quad-Tuple

Setiap klaim numerik wajib terikat 4 elemen sebelum dievaluasi:

```text
Q = < Variabel, Statistik, Nilai Numerik, Toleransi Pembulatan >  <->  Sel Tabel (baris i, kolom j)
```

| Elemen | Fungsi |
| :-- | :-- |
| Variabel | Menautkan ke baris tepat, termasuk alias (`Ukuran Perusahaan` = `SIZE`) |
| Statistik | Mengunci ke kolom metrik (`Minimum`, `Mean`, `Sig.`, dst.) |
| Nilai | Parsing desimal Indonesia, konversi `0,88` <-> `88%` |
| Toleransi | Pembulatan baku (Nuijten & Polanin, 2020) dan pemotongan desimal SPSS/Excel |

### Model AI

| Model | Peran | Ukuran | Lisensi |
| :-- | :-- | :-- | :-- |
| `BAAI/bge-reranker-v2-m3` (INT8) | Memilih baris tabel kandidat | ~570 MB | Apache-2.0 |
| `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` (INT8) | Verifikasi relasi NLI | ~270 MB | MIT |
| RapidFuzz | Pre-filter cepat dan fallback adaptif | Pustaka C | MIT |

---

## Suite 8 Solver Deterministik

| # | Solver | Landasan | Fungsi |
| :-: | :-- | :-- | :-- |
| 1 | `StatcheckSolver` | Nuijten et al. (2016) | Hitung ulang p-value dari t, F, r, chi-kuadrat, Z dan df |
| 2 | `GuardedGrimSolver` | Brown & Heathers (2017) | Cek apakah rata-rata Likert mungkin dari N bulat; menolak data kontinu |
| 3 | `GrimmerSolver` | Allard (2018) | Cek kemungkinan simpangan baku terhadap data bulat |
| 4 | `DebitSolver` | Heathers et al. (2018) | Cek mean dan SD variabel biner |
| 5 | `ConfusionMatrixAndSumAuditor` | Aljabar matriks | Cek akurasi, presisi, recall, F1, dan total 100% |
| 6 | `TupleVerificationSolver` | LOCUS Quad-Tuple | Deteksi salah ketik, transposisi digit, deviasi pembulatan |
| 7 | `FormulaEvalSolver` | Rumus statistik klasik | Hitung Z-skewness dan Z-kurtosis, bandingkan dengan klaim |
| 8 | `SuperlativeTableAuditor` | Logika komparatif | Verifikasi klaim "tertinggi/terendah/dominan" terhadap seluruh tabel |

Semua solver berjalan **tanpa LLM**.

---

## Dokumentasi API

Dokumentasi interaktif lengkap tersedia di `/docs` (Swagger) saat server berjalan.

| Method | Endpoint | Fungsi |
| :-- | :-- | :-- |
| `POST` | `/api/v1/audit` | Unggah PDF dan jalankan audit lengkap (asinkron) |
| `GET` | `/api/v1/audit/progress` | Status progres realtime |
| `POST` | `/api/v1/audit/cancel` | Batalkan audit yang berjalan |
| `GET` | `/api/v1/export-receipt` | Sertifikat audit JSON bertanda SHA-256 |

### Contoh: jalankan audit via cURL

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/audit" \
  -F "file=@skripsi_bab4.pdf"
```

### Contoh: jalankan audit via Python

```python
import requests

with open("skripsi_bab4.pdf", "rb") as f:
    r = requests.post("http://127.0.0.1:8000/api/v1/audit", files={"file": f})

data = r.json()
print("Skor kesiapan sidang:", data["readiness_score"])
for fnd in data["data"]["findings"]:
    print(fnd["severity"], fnd["claim_page"], fnd["human_explanation"])
```

### Contoh respons (ringkas)

```json
{
  "status": "success",
  "engine_version": "v3.5-grounded",
  "elapsed_seconds": 3.42,
  "readiness_score": 74.5,
  "document_sha256": "e3b0c442...b855",
  "data": {
    "document_id": "DOC-1795147392",
    "findings": [
      {
        "finding_id": "FND-001",
        "verdict": "WARN_TRUNCATION_ROUNDING",
        "severity": "warning",
        "claim_text": "variabel ini memiliki rata-rata 2,67.",
        "claim_page": 3,
        "table_ref": "Tabel 4.2",
        "table_page": 2,
        "row_category": "SQRTPGLMN",
        "stat_column": "Mean",
        "claim_value_display": "2,67",
        "table_value_display": "2.67593",
        "delta": "+0.00593",
        "human_explanation": "Nilai 2,67 merupakan pemotongan. Pembulatan baku 2 desimal adalah 2,68."
      }
    ]
  }
}
```

### Contoh: progres realtime

```json
{
  "status": "success",
  "progress": {
    "step_index": 5,
    "step_name": "Solver deterministik",
    "detail_text": "Memverifikasi klaim 45 / 120 (Hal. 7/23)",
    "percent": 68.5,
    "is_running": true,
    "cancelled": false
  }
}
```

---

## Struktur Repositori

```text
locus/
├── backend/
│   ├── main.py                     # FastAPI, routing, worker thread
│   ├── layer1_perception/
│   │   ├── pdf_reader.py
│   │   └── table_geometry.py
│   ├── layer2_core/
│   │   ├── cell_linker.py
│   │   ├── quad_tuple_verifier.py
│   │   ├── spss_likert_engine.py
│   │   ├── stat_solvers.py
│   │   ├── polarity_guard.py
│   │   └── abstention_gate.py
│   └── layer3_export/
│       ├── pii_redactor.py
│       └── revision_builder.py
├── src/core/semantic_numeric_guard.py
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── studio.html
│   └── studio.js
├── data/
│   ├── models/                     # model ONNX INT8 (unduh terpisah)
│   ├── presets/                    # contoh dokumen validasi
│   ├── rendered_pages/             # cache render halaman
│   └── uploads/                    # PDF yang diunggah
├── tests/
├── desktop_launcher.py
├── requirements.txt
└── README.md
```

---

## Pengujian

```bash
python -m pytest tests/ -v
```

| Modul tes | Cakupan |
| :-- | :-- |
| `test_realtime_progress.py` | Skema progres, pembatalan, cache model |
| `test_v35_semantic_audit.py` | Abaikan sitasi/tahun, aturan buku teks, pemisahan klausa |
| `test_api_sync.py` | Kontrak JSON, normalisasi ID tabel, tabel frekuensi SPSS |
| `test_audit_fixes.py` | Angka dempet, label variabel pendek, jumlah baris Likert |
| `test_stat_solvers.py` | Batas matematis Statcheck, GRIM, GRIMMER, DEBIT |

---

## Troubleshooting

| Masalah | Penyebab umum | Solusi |
| :-- | :-- | :-- |
| Server error saat start / model tidak ditemukan | File `.onnx` belum ada | Cek struktur `data/models/` sesuai [langkah 4](#4-siapkan-model-onnx-int8) |
| Port 8000 sudah dipakai | Aplikasi lain memakai port | Jalankan dengan `--port 8001` |
| Audit lama untuk dokumen besar | Proses di CPU lokal | Normal untuk 20-60 halaman; pantau progres atau batalkan lalu ulangi |
| Banyak temuan "unlinked" dilewati | Variabel tabel tidak cocok dengan narasi | Pastikan tabel berformat standar dan label variabel jelas |
| Pemakaian RAM tinggi | Dua model dimuat bersamaan | Tutup aplikasi lain; 16 GB RAM disarankan |
| Tabel tidak terbaca | PDF hasil scan (gambar) | Gunakan PDF teks asli (bukan hasil scan) |

---

## Privasi, Etika, dan Lisensi

- **100% offline dan zero-PII.** Dokumen diproses di perangkat Anda (`127.0.0.1`). Tidak ada data dikirim ke internet. `pii_redactor.py` menyamarkan nama mahasiswa, NIM, dan nama dosen pembimbing pada sertifikat.
- **Stack permisif.** Hanya `MIT`, `BSD-3-Clause`, dan `Apache-2.0`. Tanpa AGPL/GPL.
- **Alat bantu, bukan hakim.** Temuan LOCUS adalah petunjuk untuk diperiksa, bukan vonis pelanggaran akademik.
- **Lisensi proyek:** [MIT](LICENSE).

---

## Kontribusi

Kontribusi sangat disambut.

1. Fork repositori ini.
2. Buat branch: `git checkout -b fitur/nama-fitur`
3. Tambahkan tes untuk perubahan Anda di `tests/`.
4. Pastikan `python -m pytest tests/ -v` lulus.
5. Buka Pull Request dengan deskripsi yang jelas.

Untuk bug atau usul fitur, buka **Issues** dan sertakan: versi Python, OS, langkah reproduksi, dan (jika bisa) potongan PDF yang tidak mengandung data pribadi.

---

## Sitasi

Jika LOCUS membantu penelitian Anda:

```bibtex
@software{locus2026,
  title  = {LOCUS: Cursor for Scientific Integrity},
  author = {Tim LOCUS, Universitas Negeri Jakarta},
  year   = {2026},
  note   = {Hackvidia Arkavidia 11.0, HMIF ITB},
  url    = {https://github.com/<username>/locus}
}
```

**Referensi ilmiah:** Nuijten et al. (2016); Nuijten & Polanin (2020); Brown & Heathers (2017); Allard (2018); Heathers et al. (2018).

---

<div align="center">

Dikembangkan untuk **Hackvidia Arkavidia 11.0 (HMIF ITB)** - Subtema 4: *Learning & Self-Growth*

</div>
