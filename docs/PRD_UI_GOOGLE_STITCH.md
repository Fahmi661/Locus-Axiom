# Product Requirement Document (PRD) - UI/UX LOCUS
## Cursor for Scientific Integrity (Google Stitch Ready)

---

## 1. Executive Summary & Objective

* **Product Name:** LOCUS (/ LO-KUS /)
* **Tagline:** Offline Neuro-Symbolic Proof Engine & Dual-Pane Auditor for Scientific Integrity.
* **Target Users:** 
  1. Dosen Penguji & Pembimbing Skripsi / Tesis
  2. Juri Hackathon & Evaluator Ilmiah
  3. Mahasiswa & Peneliti Akademik
  4. Reviewer Jurnal & Editor Ilmiah
* **Core Value Proposition:** Menemukan inkonsistensi antara teks narasi klaim dan tabel empiris dalam skripsi/jurnal ilmiah dalam **di bawah 3 detik**, diverifikasi secara deterministik menggunakan solver matematika (SciPy), bebas halusinasi AI (0% false positive), dan beroperasi 100% lokal/offline (Zero-PII).
* **Goal of this PRD:** Memberikan spesifikasi visual, hierarki tata letak, kamus token desain, spesifikasi komponen mikro, serta template prompt terstruktur untuk di-generate langsung ke dalam **Google Stitch**.

---

## 2. Design System & Anti-Slop Philosophy

LOCUS mengadopsi prinsip desain **Pure Notion-Warm Editorial Minimalist**. Menghindari tampilan generic AI-slop (seperti gradien ungu neon berlebihan, kartu melayang tanpa batas tegas, atau emoji kekanak-kanakan). Tampilan harus memancarkan ketelitian, keanggunan akademis, dan keterbacaan tinggi.

### 2.1 Color Palette Tokens

| Token Name | Hex Code | Deskripsi & Penggunaan |
|---|---|---|
| `--color-paper-warmth` | `#f6f5f4` | Background utama kanvas dan halaman kerja (Notion warm paper). |
| `--color-pure-white` | `#ffffff` | Background kartu temuan, modal, dan container inspeksi. |
| `--color-ink-black` | `#111827` | Teks utama, judul, dan angka metrik penting (WCAG AAA). |
| `--color-graphite` | `#374151` | Teks sekunder, deskripsi penjelasan, dan sub-judul. |
| `--color-stone` | `#6b7280` | Metadata, nomor halaman, caption, dan border halus. |
| `--color-hairline` | `rgba(0, 0, 0, 0.08)` | Garis batas struktural kanvas dan kartu. |
| `--color-notion-blue` | `#0075de` | Aksen primer, tombol navigasi antar-halaman, dan link rujukan. |
| `--color-rose-claim` | `#e11d48` | Sorotan teks klaim bermasalah (Border: `#e11d48`, Wash: `rgba(225,29,72,0.08)`). |
| `--color-amber-evidence`| `#d97706` | Sorotan sel tabel bukti (Border: `#d97706`, Wash: `rgba(245,158,11,0.12)`). |
| `--color-emerald-pass` | `#10b981` | Status konsisten / verifikasi valid (Border: `#10b981`, Wash: `rgba(16,185,129,0.10)`). |

### 2.2 Typography Stack

* **Heading & Body Font:** Inter / -apple-system / BlinkMacSystemFont / "Segoe UI" (Sans-serif bersih, netral, berbobot 400, 500, 600, 700).
* **Mathematical & Data Font:** JetBrains Mono / SF Mono / Consolas (Monospace berjarak tetap untuk koordinat sel, angka perbandingan diff, dan formula SciPy).
* **Ukuran Tipografi:**
  - Hero Title: 32px / Line-height 1.25 / Bold 700
  - Section Header: 18px / Line-height 1.35 / Bold 700
  - Finding Card Title: 14px / Semi-bold 600
  - Diff Box Numbers: 15px / Monospace / Bold 700
  - Body Text: 13px / Line-height 1.6 / Regular 400
  - Micro Metadata: 10px-11px / Medium 500 / Letter-spacing +0.3px

### 2.3 Visual Rhythm & Spacing

* Grid: 8pt baseline grid.
* Card Corner Radius: `6px` (bukan pill bundar berlebihan, mempertahankan sudut tajam dokumen akademis).
* Shadow System: Elevasi sangat halus (`0 1px 3px rgba(0,0,0,0.04)`). Tidak ada drop shadow buram 3D.

---

## 3. Information Architecture & Screen Breakdown

LOCUS terdiri dari 2 layar utama dan 1 modal pelengkap:

```
[ SCREEN 1: LANDING & ONBOARDING ]
               │
   (Unggah PDF / Pilih Preset)
               ▼
[ SCREEN 2: DUAL-PANE AUDIT WORKSPACE ]
  ├── Panel Kiri (55%): X-Ray PDF Canvas + BBox Segments + Editorial Gutter Bracket
  └── Panel Kanan (45%): Sticky Filter Bar + 3-Second Format Cards + Mini Row Snippets
               │
   (Klik Ekspor Bukti)
               ▼
[ MODAL 3: CRYPTOGRAPHIC VERIFICATION RECEIPT ]
```

---

## 4. Spesifikasi Detil Layar (Screen by Screen)

### Layar 1: Landing, Showcase Solvers & Upload Onboarding

#### Header / Navigation Bar
* **Kiri:** Logo tipografis `LOCUS` bersanding dengan subtitle kecil `Cursor for Scientific Integrity`.
* **Kanan:** Indikator status mesin (`Local Engine Active · 100% Offline`), tombol dokumentasi, dan tautan GitHub/Arkavidia.

#### Hero Section
* **Academic Kicker Strip:** Label ringkas di atas judul: `STANDAR VERIFIKASI AKADEMIK · ARKAVヌDIA 11.0 HMIF ITB`.
* **Headline:** "Audit Integritas Data Skripsi & Makalah Ilmiah dalam Hitungan Detik."
* **Sub-headline:** "Neuro-symbolic proof engine yang secara otomatis menautkan klaim kalimat ke tabel empiris, memverifikasi konsistensi matematika murni, dan menjamin 0% false positive."
* **Trust Badges Strip:**
  - 8 Mesin Solver Deterministik (Statcheck, GRIM, GRIMMER, DEBIT, Steeper Total-N, Confusion Matrix, Tuple Verifier, SymPy Formula).
  - Garansi 0% False Positive (Gerbang Abstensi Tau-Link >= 0.75).
  - 100% Offline & Zero-PII (Data tidak pernah keluar dari memori lokal komputer).

#### Interactive Golden Presets Bar (Untuk Pengujian Panggung / Juri)
Tiga tombol cepat untuk memuat kasus uji nyata tanpa harus mencari berkas PDF:
1. **Preset 1:** *Evaluasi Model ML* (Inversi Polaritas Metrik Galat RMSE vs Akurasi).
2. **Preset 2:** *Uji Prasyarat Normalitas* (Jebakan Sidang: Nilai Sig. < 0,05 disimpulkan normal).
3. **Preset 3:** *Uji-t Eksperimen* (Pembalikan Keputusan Signifikansi Statcheck p=0,002 vs p=0,019).

#### Upload Dropzone
* Area drag-and-drop dokumen PDF bergaris putus-putus elegan (`border: 1.5px dashed rgba(0,0,0,0.15)`).
* Pesan instruksi: "Tarik & letakkan berkas PDF skripsi (Bab 4/Bab 3) atau klik untuk memilih berkas".
* Indikator kompatibilitas: "Mendukung format naskah skripsi Indonesia, SPSS, R, dan format publikasi IEEE/APA".

---

### Layar 2: Dual-Pane Audit Workspace (Antarmuka Inti)

Layar ini menggunakan pembagian layar terbelah (*split canvas*) responsif:

```
┌──────────────────────────────────────────────┬──────────────────────────────────────────────┐
│  TOP TOOLBAR: Judul Dokumen · Paginasi [ < 3/18 > ] · Zoom [ - 100% + ] · Tombol Ekspor      │
├──────────────────────────────────────────────┼──────────────────────────────────────────────┤
│  PANEL KIRI (55%): PDF X-RAY CANVAS          │  PANEL KANAN (45%): EVIDENCE INSPECTOR       │
│                                              │                                              │
│  [Gutter] [Teks Halaman PDF Asli]            │  [ Sticky Filter: Semua | Beda Tabel | Ralat ]│
│     │                                        │                                              │
│     ├── Kotak Klaim Merah Muda (Line-by-Line)│  ┌── KARTU TEMUAN 3-DETIK ─────────────────┐  │
│     │   (Menyorot kalimat yang diuji)        │  │ [Badge Status] Salah Pembulatan Angka   │  │
│     │                                        │  │                                         │  │
│     └── Bracket Gutter Margin Kiri           │  │ ┌── KOTAK PERBANDINGAN BERDAMPINGAN ──┐ │  │
│         (Jalur garis rapi tanpa motong teks) │  │ │ Tertulis di Teks: │ Tertera di Tabel:│ │  │
│                                              │  │ │     2,67          ➔    2.6759       │ │  │
│     ┌──────────────────────────────────┐     │  │ │                   │  (Baku: 2,68)   │ │  │
│     │ TABEL BUKTI EMPIRIS              │     │  │ └───────────────────────────────────┘ │  │
│     │ [Baris SQRTPGLMN]                │     │  │ Penjelasan: Penulis memotong desimal... │  │
│     │ [Sel Mean: 2.6759...] (Kuning)   │     │  ├─────────────────────────────────────────┤  │
│     └──────────────────────────────────┘     │  │ ▦ Cuplikan Baris Tabel Bukti (Hal. 2)   │  │
│                                              │  │ [DELAY: 76.4 | SQRTPGLMN: 2.6759* | ..] │  │
│                                              │  │ [Tombol: Lompat ke Tabel (Hal. 2) ↗]    │  │
│                                              │  ├─────────────────────────────────────────┤  │
│                                              │  │ Kutipan Kalimat Teks Mahasiswa          │  │
│                                              │  │ Bukti Matematika SciPy & What-If Live   │  │
│                                              │  │ Kuis Pembelajaran (Pedagogical MCQ)     │  │
│                                              │  └─────────────────────────────────────────┘  │
└──────────────────────────────────────────────┴──────────────────────────────────────────────┘
```

#### Spesifikasi Panel Kiri: High-Precision PDF X-Ray Canvas
1. **Interactive Multi-Line Highlight (`xray-line-segment`):**
   - Kotak highlight merah muda tidak membungkus blok persegi besar yang meluap ke kalimat lain.
   - Menggunakan highlight segmental per baris teks kalimat yang diuji (`rgba(225, 29, 72, 0.12)` dengan border `1.5px solid #e11d48`).
2. **Table Evidence Cell Pins:**
   - Sel tabel yang menjadi rujukan ditandai dengan kotak kuning ambar (`rgba(245, 158, 11, 0.14)` dengan border `1.5px solid #d97706`).
   - Interior sel tetap 100% transparan agar angka asli tabel di PDF tetap terbaca jelas oleh mata penguji.
3. **Editorial Margin Gutter Bracket (Bukan Garis Silang):**
   - Jalur penghubung antara klaim narasi dan sel tabel ditarik melalui gutter margin kiri (`x = 14px`) menggunakan kurva lengkung kubik `M ... C ...`. Garis **tidak pernah memotong teks dokumen** sehingga estetika kertas skripsi tetap terjaga.

#### Spesifikasi Panel Kanan: Kartu Temuan "Mudah Dibaca dalam 3 Detik"
Setiap kartu temuan diwajibkan menyajikan hirarki informasi dengan urutan berikut:

1. **Header Kartu:**
   - Judul Bahasa Indonesia Ramah Awam (Huruf tebal 14px):
     * *Salah Pembulatan Angka* (menggantikan `WARN_TRUNCATION_ROUNDING`)
     * *Angka Berbeda dengan Tabel* (menggantikan `DIRECT_CELL_CONTRADICTION`)
     * *Salah Ketik Digit (Transposisi)* (menggantikan `DIGIT_TRANSPOSITION_TYPO`)
     * *Logika Uji Prasyarat Terbalik* (menggantikan `PREREQUISITE_LOGIC_INVERSION`)
     * *Pembalikan Keputusan Signifikansi* (menggantikan `DECISION_FLIP`)
   - Badge kode teknis kecil di samping (`F-C_3_21-TUPLE · Hal. 3`).

2. **Diff 3-Second Format Box (Wajib di Paling Atas):**
   - **Kolom Kiri (Aksen Merah Muda):**
     * Label: `Tertulis di Kalimat (Hal. X):`
     * Angka: Nilai yang ditulis mahasiswa dalam teks narasi (contoh: `2,67`).
   - **Ikon Panah Tengah:** `➔`
   - **Kolom Kanan (Aksen Kuning Ambar):**
     * Label: `Tertera di Tabel (Hal. Y):`
     * Angka: Nilai eksak sel tabel asli (contoh: `2.67593335`) + Badge Pembulatan Baku `(Baku: 2,68)`.
   - **Callout Penjelasan Singkat (1 Kalimat):**
     * Strip latar belakang biru muda dengan border kiri biru: "Penulis memotong desimal angka menjadi 2,67, padahal aturan pembulatan baku matematika seharusnya dibulatkan ke atas menjadi 2,68."

3. **Cuplikan Baris Tabel Langsung (Mini Table Row Snippet):**
   - Menampilkan mini tabel 1 baris yang langsung memperlihatkan baris variabel terkait beserta seluruh nama kolomnya.
   - Sel target ditandai dengan warna ambar dan badge `Bukti`.
   - Disertai tombol navigasi: `[Lompat ke Tabel (Hal. Y) ↗]` sehingga penguji tidak perlu repot mencari manual halaman tabel.

4. **Kutipan Kalimat Asli:**
   - Kotak kutipan bergaris batas kiri lembut berisi kalimat lengkap mahasiswa yang diperiksa.

5. **Bukti Matematika Deterministik (SciPy Callout):**
   - Menampilkan rumus rekalkulasi baku ilmiah secara rapi (contoh: `SQRTPGLMN.Mean: Sel = 2.67593 -> Pembulatan 2 desimal = 2.68 != 2.67`).

6. **Interactive What-If Live Stepper:**
   - Tombol step `[ − ]` dan `[ + ]` dengan delta `±0.01` untuk mensimulasikan nilai batas kritis di mana temuan berubah status secara live.

7. **Explain-First Pedagogical Scaffolding:**
   - Pertanyaan pilihan ganda mendidik (Multiple Choice Question) untuk menguji pemahaman mahasiswa/peneliti mengapa hal tersebut keliru.
   - Draf usulan kalimat revisi ilmiah yang aman dan siap disalin ke dalam dokumen.

---

### Layar 3: Cryptographic Verification Receipt (Modal Ekspor)

* Ringkasan audit dokumen: Tanggal audit, durasi komputasi (<200 ms), total klaim terperiksa, dan persentase kepatuhan integritas data.
* **Hash Kriptografis SHA-256:** Tanda tangan unik berkas PDF untuk memastikan dokumen tidak dimanipulasi setelah diaudit.
* **Tabel Verifikasi Terperinci:** Daftar seluruh temuan lengkap dengan koordinat bounding box, status verifikasi, dan solver yang memverifikasi.
* **Opsi Redaksi PII (Privasi):** Toggle sakelar untuk menyamarkan nama mahasiswa, NIM, nama dosen pembimbing, dan institusi sebelum tanda terima dicetak/diekspor ke format PDF/JSON.

---

## 5. Structured Prompts untuk Google Stitch

Salin dan gunakan blok prompt berikut saat mendesain antarmuka di **Google Stitch**:

### Prompt Stitch 1: Global Theme & Workspace Layout
```text
Design a clean, professional academic document audit interface inspired by Notion's warm paper aesthetic and modern scientific tools.
Color Palette:
- Canvas Background: #f6f5f4 (warm muted paper)
- Card Surfaces: #ffffff (pure white with 1px border rgba(0,0,0,0.08))
- Primary Accent: #0075de (deep notion blue)
- Error / Contradiction: #e11d48 (rose pink)
- Table Evidence: #d97706 (warm amber)
- Consistent / Pass: #10b981 (emerald green)
- Typography: Inter for UI and JetBrains Mono for numbers, coordinates, and formulas.

Layout Structure:
1. Top Bar: App title "LOCUS", Document name "BAB 4 Skripsi.pdf", Page navigation controls with previous/next buttons, Zoom controls [ - ] [ 100% ] [ + ] [ Fit ], and an "Ekspor Bukti" button.
2. Dual-Pane Workspace:
   - Left Pane (55% width): Centered authentic PDF viewer rendering thesis pages on warm paper with page shadow.
   - Right Pane (45% width): Findings inspector with sticky filter pills ("Semua", "Inkonsistensi Fatal", "Peringatan Pembulatan", "Konsisten").
```

### Prompt Stitch 2: Finding Card Component (3-Second Format)
```text
Design a specialized "Finding Card" for an academic paper audit tool that can be understood by non-technical thesis examiners in under 3 seconds:

Card Elements (Top to Bottom):
1. Card Header:
   - Left: Rounded status tag with a colored status dot and clear Indonesian title: "Salah Pembulatan Angka" (amber) or "Angka Berbeda dengan Tabel" (rose). Small monospace code tag next to it: "WARN_TRUNCATION_ROUNDING".
   - Right: Subtle metadata label "F-C_3_21-TUPLE · Hal. 3".
2. Diff Comparison Box (Prominent at the very top):
   - Two equal columns side-by-side with an arrow (➔) in between:
     * Left Column (Claimed): Label "Tertulis di Kalimat (Hal. 3)" in small caps, with big bold number "2,67" in rose color.
     * Right Column (Table Evidence): Label "Tertera di Tabel (Hal. 2)" in small caps, with bold number "2.6759" in amber color and a pill badge "(Baku: 2,68)".
   - Bottom full-width callout in light blue tint with blue left border: "Penjelasan Singkat: Penulis memotong desimal menjadi 2,67 padahal pembulatan baku matematika seharusnya ke atas menjadi 2,68."
3. Table Row Snippet Preview:
   - Header with table icon, title "Cuplikan Baris Tabel: Tabel 4.2 (Hal. 2)", and a button "Lompat ke Tabel (Hal. 2) ↗".
   - A clean 1-row table preview showing headers (Baris, N, Minimum, Maximum, Mean, Std. Dev) and cells. The Mean cell "2.6759" is highlighted in soft amber with a small "Bukti" badge.
4. Quoted Student Sentence:
   - Elegant blockquote with light grey left border showing the sentence: "Selanjutnya adalah pengalaman auditor (PNGLM)... dengan rata-rata 2,67."
5. SciPy Mathematical Recalculation box with monospace formula.
6. What-If Stepper control [-] 2.6759 [+] with a "Live Re-calc" status badge.
7. Multiple Choice Quiz question with 2 clickable option cards and a hidden recommended revision box.
```

### Prompt Stitch 3: PDF Document Overlay & Evidence Connecting Line
```text
Design the visual overlay layer on top of a rendered academic PDF page:
1. Claim Highlight:
   - A sentence spanning two lines is highlighted using two individual tight rounded rectangle segments wrapping only the text of those two lines, with border 1.5px solid #e11d48 and a soft translucent pink fill rgba(225,29,72,0.12).
   - A small floating tag above the sentence reads: "Klaim Terpilih · Bukti di Hal. 2 ↗".
2. Table Cell Highlight:
   - In a descriptive statistics table, a specific cell under the "Mean" column is outlined with 1.5px solid #d97706 and transparent inner background so the printed numbers remain 100% legible.
3. Editorial Margin Bracket:
   - An elegant bracket line located strictly inside the left document margin (x = 14px) curves gently from the claim sentence level down to the table level, with an arrow pointing toward the table, completely avoiding crossing over any printed document text.
```

---

## 6. Kriteria Keberhasilan Tampilan (Acceptance Criteria)

1. **Kejelasan Waktu Baca (3-Second Rule):**
   - Juri atau penguji skripsi dapat mengenali angka teks, angka tabel asli, dan kesimpulan kesalahannya dalam $\le 3$ detik tanpa perlu membaca formula SciPy mentah.
2. **Presisi Penyorotan BBox:**
   - Tidak ada kotak highlight yang menabrak kalimat di atas atau di bawahnya. Kalimat 2 baris disorot per baris secara akurat.
3. **Keterbacaan Lintas Halaman:**
   - Setiap temuan lintas halaman (misal: klaim di Hal. 3, tabel di Hal. 2) menampilkan cuplikan mini baris tabel langsung di kartu kanan, mengeliminasi kebutuhan bolak-balik halaman secara manual.
4. **Bebas Tipografi AI-Slop:**
   - Tidak ada karakter strip panjang em dash, tidak ada kartu gradien ungu menyilaukan, dan seluruh teks antarmuka menggunakan bahasa Indonesia baku yang formal dan lugas.
