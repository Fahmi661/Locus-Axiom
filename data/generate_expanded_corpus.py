"""
LOCUS Synthetic Academic Corpus Generator
Generates 10 realistic multi-page academic PDF manuscripts across diverse faculties:
1. CS / NLP: Model Deep Learning & Transformer (BLEU, Perplexity, WER, Acc)
2. FEB / Accounting: Rasio Keuangan Perbankan BEI (CAR, NPL, ROA, LDR)
3. Psikologi: Skala Resiliensi Psikologis Likert (GRIM, paritas varians, Cronbach)
4. Kedokteran: Uji Klinis Terapi Obat (Odds Ratio, Chi-Square, t-test)
5. Pendidikan: Eksperimen Pembelajaran STEM (N-Gain, Paired t-test)
6. Statistika: Uji Asumsi Regresi Berganda (VIF, Durbin-Watson, Glejser)
7. Data Science: Evaluasi Clustering & Segmentasi (Silhouette, Davies-Bouldin)
8. Teknik Industri: Pengendalian Kualitas & Kapabilitas Proses (Cp, Cpk, ANOVA F)
9. AI / Vision: Deteksi Objek Real-Time (mAP50, mAP50-95, Latensi FPS)
10. Dokumen Kontrol: Naskah Publikasi Bersih 100% Konsisten (True Negative Benchmark)
"""

import os
from fpdf import FPDF

class AcademicPdf(FPDF):
    def __init__(self, doc_title: str):
        super().__init__()
        self.doc_title = doc_title

    def header(self):
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"LOCUS Academic Benchmark Corpus -- {self.doc_title}", 0, 1, "R")
        self.set_line_width(0.2)
        self.set_draw_color(200, 200, 200)
        self.line(10, 15, 200, 15)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Halaman {self.page_no()}", 0, 0, "C")

    def draw_3line_table(self, title: str, headers: list, rows: list, col_widths: list, alignments: list = None):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(30, 30, 30)
        self.cell(0, 6, title, 0, 1, "L")
        self.ln(1)

        total_w = sum(col_widths)
        start_x = self.get_x()

        # Top Line
        self.set_line_width(0.5)
        self.set_draw_color(0, 0, 0)
        self.line(start_x, self.get_y(), start_x + total_w, self.get_y())

        # Header
        self.set_font("Helvetica", "B", 9)
        for i, h in enumerate(headers):
            align = alignments[i] if alignments else ("L" if i == 0 else "C")
            self.cell(col_widths[i], 7, h, 0, 0, align)
        self.ln(7)

        # Mid Line
        self.set_line_width(0.3)
        self.line(start_x, self.get_y(), start_x + total_w, self.get_y())

        # Rows
        self.set_font("Helvetica", "", 9)
        for row in rows:
            for i, val in enumerate(row):
                align = alignments[i] if alignments else ("L" if i == 0 else "C")
                self.cell(col_widths[i], 6, str(val), 0, 0, align)
            self.ln(6)

        # Bottom Line
        self.set_line_width(0.5)
        self.line(start_x, self.get_y(), start_x + total_w, self.get_y())
        self.ln(4)


def generate_all_expanded_pdfs(target_dir: str):
    os.makedirs(target_dir, exist_ok=True)

    # 1. CS Deep Learning NLP
    pdf1 = AcademicPdf("Informatika: Deep Learning NLP")
    pdf1.add_page()
    pdf1.set_font("Helvetica", "B", 13)
    pdf1.cell(0, 8, "BAB IV: HASIL DAN PEMBAHASAN", 0, 1, "C")
    pdf1.ln(2)
    pdf1.set_font("Helvetica", "B", 11)
    pdf1.cell(0, 6, "4.1 Evaluasi Model Bahasa dan Terjemahan Mesin", 0, 1, "L")
    pdf1.set_font("Helvetica", "", 10)
    pdf1.multi_cell(0, 5.5, (
        "Berdasarkan pengujian pada dataset IndoNLG, performa arsitektur transformer dievaluasi "
        "menggunakan metrik BLEU Score, Perplexity, Word Error Rate (WER), dan Akurasi. "
        "Hasil pengujian selengkapnya disajikan pada Tabel 4.1."
    ))
    pdf1.ln(3)
    pdf1.draw_3line_table(
        "Tabel 4.1 Perbandingan Performa Arsitektur Model Bahasa",
        ["Model Arsitektur", "BLEU", "Perplexity", "WER (%)", "Akurasi"],
        [
            ["IndoBERT-Base", "34,25", "18,40", "12,8", "0,89"],
            ["IndoBART-Large", "41,80", "11,25", "8,4", "0,94"],
            ["mT5-Base", "38,50", "14,60", "10,5", "0,91"]
        ],
        [50, 30, 35, 35, 30]
    )
    pdf1.set_font("Helvetica", "", 10)
    # INJECTED POLARITY ERROR: Model IndoBERT diklaim terbaik karena Perplexity tertinggi
    pdf1.multi_cell(0, 5.5, (
        "Berdasarkan Tabel 4.1 di atas, arsitektur IndoBART-Large menunjukkan nilai BLEU tertinggi yaitu 41,80 "
        "dan akurasi 0,94. Namun peneliti menyimpulkan bahwa IndoBERT-Base memiliki kinerja generasi paling optimal "
        "karena menghasilkan nilai Perplexity tertinggi sebesar 18,40 dibandingkan model lainnya."
    ))
    pdf1.output(os.path.join(target_dir, "DOC-SKRIPSI-CS-01_Deep_Learning_NLP.pdf"))

    # 2. FEB Rasio Keuangan Perbankan
    pdf2 = AcademicPdf("Ekonomi: Rasio Keuangan Perbankan BEI")
    pdf2.add_page()
    pdf2.set_font("Helvetica", "B", 13)
    pdf2.cell(0, 8, "BAB IV: ANALISIS STATISTIK DESKRIPTIF", 0, 1, "C")
    pdf2.ln(2)
    pdf2.set_font("Helvetica", "B", 11)
    pdf2.cell(0, 6, "4.2 Deskripsi Variabel Kinerja Keuangan", 0, 1, "L")
    pdf2.set_font("Helvetica", "", 10)
    pdf2.multi_cell(0, 5.5, (
        "Penelitian ini menggunakan 40 observasi perbankan yang terdaftar di Bursa Efek Indonesia periode 2020-2023. "
        "Variabel yang dianalisis mencakup Capital Adequacy Ratio (CAR), Non-Performing Loan (NPL), "
        "dan Return on Assets (ROA)."
    ))
    pdf2.ln(3)
    pdf2.draw_3line_table(
        "Tabel 4.2 Statistik Deskriptif Rasio Keuangan Perbankan (N=40)",
        ["Variabel", "N", "Minimum", "Maximum", "Mean", "Std. Dev"],
        [
            ["CAR (%)", "40", "14,50", "26,80", "20,45", "3,12"],
            ["NPL (%)", "40", "1,20", "4,80", "2,75", "0,85"],
            ["ROA (%)", "40", "0,80", "3,65", "1,8549", "0,64"]
        ],
        [40, 20, 30, 30, 35, 30]
    )
    pdf2.set_font("Helvetica", "", 10)
    # INJECTED TRUNCATION ERROR on ROA: 1.8549 rounds to 1.85, written 1.85 (consistent)
    # Injected TYPO on CAR: max 26.80 written as 20.68
    pdf2.multi_cell(0, 5.5, (
        "Berdasarkan Tabel 4.2 di atas, rasio kecukupan modal (CAR) memiliki nilai minimum 14,50 "
        "dengan tingkat tertinggi pada 20,68 dan rata-rata 20,45. "
        "Sementara itu rasio NPL terendah adalah 1,20 dan rata-rata 2,75."
    ))
    pdf2.output(os.path.join(target_dir, "DOC-SKRIPSI-FEB-02_Rasio_Keuangan_Perbankan.pdf"))

    # 3. Psikologi Skala Resiliensi Likert (GRIM Test)
    pdf3 = AcademicPdf("Psikologi: Skala Resiliensi Mahasiswa")
    pdf3.add_page()
    pdf3.set_font("Helvetica", "B", 13)
    pdf3.cell(0, 8, "BAB IV: HASIL PENGUKURAN PSIKOLOGI", 0, 1, "C")
    pdf3.ln(2)
    pdf3.set_font("Helvetica", "B", 11)
    pdf3.cell(0, 6, "4.1 Deskripsi Resiliensi Akademik (Skala Likert 1-5)", 0, 1, "L")
    pdf3.set_font("Helvetica", "", 10)
    pdf3.multi_cell(0, 5.5, (
        "Pengukuran resiliensi akademik dilakukan terhadap sampel 20 mahasiswa tingkat akhir (N=20) "
        "menggunakan kuesioner skala Likert bilangan bulat 1 sampai 5. Nilai rata-rata dan simpangan baku "
        "disajikan pada Tabel 4.3 berikut:"
    ))
    pdf3.ln(3)
    pdf3.draw_3line_table(
        "Tabel 4.3 Hasil Uji Skala Resiliensi Mahasiswa (N=20)",
        ["Dimensi Resiliensi", "N", "Mean", "Std. Dev"],
        [
            ["Kegigihan", "20", "3,45", "0,68"],
            ["Regulasi Emosi", "20", "3,28", "0,74"],
            ["Optimisme", "20", "3,60", "0,55"]
        ],
        [60, 30, 45, 45]
    )
    pdf3.set_font("Helvetica", "", 10)
    # INJECTED GRIM ERROR: Mean 3.28 on N=20 -> 20 * 3.28 = 65.6 (nearest int is 66 -> 66/20 = 3.30 != 3.28)
    pdf3.multi_cell(0, 5.5, (
        "Berdasarkan Tabel 4.3, dimensi kegigihan menghasilkan nilai rata-rata sebesar 3,45. "
        "Untuk dimensi regulasi emosi, diperoleh nilai mean sebesar 3,28 dengan standar deviasi 0,74 "
        "pada jumlah sampel sebanyak 20 responden."
    ))
    pdf3.output(os.path.join(target_dir, "DOC-SKRIPSI-PSI-03_Skala_Resiliensi_Psikologi.pdf"))

    # 4. Kedokteran Uji Klinis & Uji-t (Statcheck Decision Flip)
    pdf4 = AcademicPdf("Kedokteran: Uji Klinis Terapi")
    pdf4.add_page()
    pdf4.set_font("Helvetica", "B", 13)
    pdf4.cell(0, 8, "BAB IV: HASIL UJI KLINIS FARMAKOLOGI", 0, 1, "C")
    pdf4.ln(2)
    pdf4.set_font("Helvetica", "B", 11)
    pdf4.cell(0, 6, "4.3 Efektivitas Terapi Kombinasi vs Kontrol", 0, 1, "L")
    pdf4.set_font("Helvetica", "", 10)
    pdf4.multi_cell(0, 5.5, (
        "Uji efektivitas penurunan biomarker inflamasi diuji menggunakan Independent Samples t-test. "
        "Kelompok perlakuan menunjukkan reduksi yang dibandingkan terhadap plasebo."
    ))
    pdf4.ln(3)
    pdf4.draw_3line_table(
        "Tabel 4.4 Hasil Uji-t Perbandingan Penurunan Biomarker",
        ["Kelompok", "N", "Mean Reduksi", "t-statistic", "df", "p-value"],
        [
            ["Terapi Kombinasi", "30", "14,80", "2,15", "58", "0,036"],
            ["Kontrol Plasebo", "30", "8,20", "-", "-", "-"]
        ],
        [45, 20, 35, 30, 25, 25]
    )
    pdf4.set_font("Helvetica", "", 10)
    # INJECTED STATCHECK FLIP: t(58) = 1.68 claimed p = 0.021 (actually p = 0.098, not significant)
    pdf4.multi_cell(0, 5.5, (
        "Pada uji biomarker lanjutan terhadap enzim sekunder, diperoleh hasil uji t ( 58 ) = 1.68 "
        "dengan nilai signifikansi p = 0.021 sehingga peneliti menyimpulkan terdapat perbedaan yang sangat signifikan "
        "antara kedua kelompok terapi."
    ))
    pdf4.output(os.path.join(target_dir, "DOC-SKRIPSI-MED-04_Uji_Klinis_Farmakologi.pdf"))

    # 5. Pendidikan Uji N-Gain & Pembelajaran STEM
    pdf5 = AcademicPdf("Pendidikan: Pembelajaran STEM")
    pdf5.add_page()
    pdf5.set_font("Helvetica", "B", 13)
    pdf5.cell(0, 8, "BAB IV: HASIL PENELITIAN DAN PEMBAHASAN", 0, 1, "C")
    pdf5.ln(2)
    pdf5.set_font("Helvetica", "B", 11)
    pdf5.cell(0, 6, "4.2 Peningkatan Hasil Belajar Berbasis Model STEM", 0, 1, "L")
    pdf5.set_font("Helvetica", "", 10)
    pdf5.multi_cell(0, 5.5, (
        "Penelitian ini menerapkan model pembelajaran STEM terintegrasi pada siswa kelas XI (N=32). "
        "Rata-rata nilai pretest, posttest, dan N-gain ternormalisasi disajikan pada Tabel 4.5."
    ))
    pdf5.ln(3)
    pdf5.draw_3line_table(
        "Tabel 4.5 Hasil Pengukuran Pretest, Posttest, dan N-Gain",
        ["Tahap Pengukuran", "N", "Nilai Minimum", "Nilai Maksimum", "Rata-rata", "Std Dev"],
        [
            ["Pretest", "32", "38,00", "65,00", "51,25", "6,80"],
            ["Posttest", "32", "72,00", "96,00", "84,50", "5,40"],
            ["N-Gain Score", "32", "0,45", "0,88", "0,68", "0,11"]
        ],
        [45, 18, 32, 32, 30, 25]
    )
    pdf5.set_font("Helvetica", "", 10)
    # CLEAN ACCURATE REPORTING
    pdf5.multi_cell(0, 5.5, (
        "Berdasarkan Tabel 4.5, nilai pretest siswa memiliki nilai minimum 38,00 dan nilai maksimum 65,00 "
        "dengan rata-rata 51,25. Setelah implementasi model STEM, rata-rata nilai posttest meningkat menjadi 84,50 "
        "dengan rata-rata N-Gain sebesar 0,68 yang tergolong dalam kategori efektivitas sedang."
    ))
    pdf5.output(os.path.join(target_dir, "DOC-SKRIPSI-EDU-05_Eksperimen_Pembelajaran_STEM.pdf"))

    # 6. Statistika Uji Asumsi Klasik (Prerequisite Logic Inversion)
    pdf6 = AcademicPdf("Statistika: Uji Asumsi Klasik Regresi")
    pdf6.add_page()
    pdf6.set_font("Helvetica", "B", 13)
    pdf6.cell(0, 8, "BAB IV: UJI ASUMSI KLASIK DAN REGRESI", 0, 1, "C")
    pdf6.ln(2)
    pdf6.set_font("Helvetica", "B", 11)
    pdf6.cell(0, 6, "4.1 Uji Normalitas dan Homogenitas Varians", 0, 1, "L")
    pdf6.set_font("Helvetica", "", 10)
    pdf6.multi_cell(0, 5.5, (
        "Sebelum dilakukan uji regresi linear berganda, seluruh data residual model harus diuji "
        "apakah memenuhi asumsi normalitas melalui uji Kolmogorov-Smirnov."
    ))
    pdf6.ln(3)
    pdf6.draw_3line_table(
        "Tabel 4.6 Hasil Uji Normalitas One-Sample Kolmogorov-Smirnov",
        ["Parameter Uji", "Residual Model Regresi"],
        [
            ["N Sampel", "80"],
            ["Kolmogorov-Smirnov Z", "1,85"],
            ["Asymp. Sig. (2-tailed)", "0,012"]
        ],
        [90, 90]
    )
    pdf6.set_font("Helvetica", "", 10)
    # INJECTED INVERSION ERROR: Sig = 0.012 claimed as NORMAL
    pdf6.multi_cell(0, 5.5, (
        "Berdasarkan hasil uji Kolmogorov-Smirnov pada Tabel 4.6, diperoleh nilai Asymp. Sig. sebesar 0,012. "
        "Oleh karena nilai signifikansi lebih kecil dari 0,05, peneliti menyimpulkan bahwa data terdistribusi secara normal "
        "dan asumsi klasik normalitas terpenuhi."
    ))
    pdf6.output(os.path.join(target_dir, "DOC-JURNAL-STAT-06_Uji_Asumsi_Regresi.pdf"))

    # 7. Data Science Clustering & Segmentasi
    pdf7 = AcademicPdf("Data Science: Evaluasi Segmentasi Pelanggan")
    pdf7.add_page()
    pdf7.set_font("Helvetica", "B", 13)
    pdf7.cell(0, 8, "BAB IV: HASIL CLUSTERING DAN SEGMENTASI", 0, 1, "C")
    pdf7.ln(2)
    pdf7.set_font("Helvetica", "B", 11)
    pdf7.cell(0, 6, "4.3 Evaluasi Kualitas Partisi Klaster", 0, 1, "L")
    pdf7.set_font("Helvetica", "", 10)
    pdf7.multi_cell(0, 5.5, (
        "Evaluasi kualitas pemisahan klaster dilakukan dengan membandingkan metrik Silhouette Score, "
        "Davies-Bouldin Index (DBI), dan Calinski-Harabasz Index."
    ))
    pdf7.ln(3)
    pdf7.draw_3line_table(
        "Tabel 4.7 Evaluasi Metrik Kualitas Klaster K-Means (k=3 s.d. k=5)",
        ["Jumlah Klaster (k)", "Silhouette Score", "Davies-Bouldin Index", "Calinski-Harabasz"],
        [
            ["k = 3", "0,68", "0,54", "1420,5"],
            ["k = 4", "0,52", "0,82", "1180,2"],
            ["k = 5", "0,44", "1,15", "950,8"]
        ],
        [45, 45, 50, 40]
    )
    pdf7.set_font("Helvetica", "", 10)
    # INJECTED POLARITY ERROR on DBI: higher DBI claimed as best
    pdf7.multi_cell(0, 5.5, (
        "Berdasarkan Tabel 4.7, konfigurasi k = 3 menghasilkan nilai Silhouette Score tertinggi sebesar 0,68. "
        "Namun peneliti memilih konfigurasi k = 5 sebagai model klaster terbaik karena menghasilkan "
        "nilai Davies-Bouldin Index tertinggi sebesar 1,15."
    ))
    pdf7.output(os.path.join(target_dir, "DOC-SKRIPSI-DS-07_Segmentasi_Clustering.pdf"))

    # 8. Teknik Industri Pengendalian Kualitas
    pdf8 = AcademicPdf("Teknik Industri: Kapabilitas Proses")
    pdf8.add_page()
    pdf8.set_font("Helvetica", "B", 13)
    pdf8.cell(0, 8, "BAB IV: ANALISIS KAPABILITAS PROSES PRODUKSI", 0, 1, "C")
    pdf8.ln(2)
    pdf8.set_font("Helvetica", "B", 11)
    pdf8.cell(0, 6, "4.2 Indeks Kapabilitas Mesin Milling CNC", 0, 1, "L")
    pdf8.set_font("Helvetica", "", 10)
    pdf8.multi_cell(0, 5.5, (
        "Analisis pengendalian mutu dimensi poros baja dilakukan pada 50 sampel pengukuran toleransi (N=50). "
        "Nilai statistik deskriptif dan indeks kapabilitas disajikan pada Tabel 4.8."
    ))
    pdf8.ln(3)
    pdf8.draw_3line_table(
        "Tabel 4.8 Parameter Kapabilitas Proses Poros Baja (N=50)",
        ["Parameter", "Nilai", "Batas Bawah", "Batas Atas"],
        [
            ["Mean Diameter (mm)", "25,02", "24,95", "25,05"],
            ["Standar Deviasi", "0,018", "-", "-"],
            ["Indeks Cp", "1,48", "1,33", "-"],
            ["Indeks Cpk", "1,35", "1,33", "-"]
        ],
        [60, 40, 40, 40]
    )
    pdf8.set_font("Helvetica", "", 10)
    # CLEAN REPORTING
    pdf8.multi_cell(0, 5.5, (
        "Berdasarkan Tabel 4.8, rata-rata diameter poros baja tercatat sebesar 25,02 mm dengan standar deviasi "
        "sebesar 0,018. Nilai indeks kapabilitas proses Cp sebesar 1,48 dan Cpk sebesar 1,35 berada di atas standar "
        "minimum 1,33 yang menandakan proses produksi berada dalam kondisi terkendali dan kapabel."
    ))
    pdf8.output(os.path.join(target_dir, "DOC-SKRIPSI-TIN-08_Kapabilitas_Proses.pdf"))

    # 9. AI Computer Vision Deteksi Objek
    pdf9 = AcademicPdf("AI: Deteksi Objek Real-Time")
    pdf9.add_page()
    pdf9.set_font("Helvetica", "B", 13)
    pdf9.cell(0, 8, "BAB IV: PERFORMA DETEKSI OBJEK CITRA DRONE", 0, 1, "C")
    pdf9.ln(2)
    pdf9.set_font("Helvetica", "B", 11)
    pdf9.cell(0, 6, "4.4 Perbandingan Model YOLOv8 vs RT-DETR", 0, 1, "L")
    pdf9.set_font("Helvetica", "", 10)
    pdf9.multi_cell(0, 5.5, (
        "Pengujian komparatif model deteksi objek kendaraan pada citra udara dievaluasi pada resolusi 640x640 "
        "menggunakan metrik mAP50, mAP50-95, dan Latensi Inferensi."
    ))
    pdf9.ln(3)
    pdf9.draw_3line_table(
        "Tabel 4.9 Perbandingan Performa Arsitektur Detektor Objek",
        ["Model Arsitektur", "mAP@50", "mAP@50-95", "Latensi (ms)", "Throughput (FPS)"],
        [
            ["YOLOv8-Small", "0,845", "0,612", "12,4", "80,6"],
            ["YOLOv8-Medium", "0,892", "0,684", "24,8", "40,3"],
            ["RT-DETR-Base", "0,875", "0,650", "35,2", "28,4"]
        ],
        [45, 32, 35, 35, 35]
    )
    pdf9.set_font("Helvetica", "", 10)
    # INJECTED ROUNDING TRUNCATION: mAP50 0.845 rounds to 0.85, written 0.84
    pdf9.multi_cell(0, 5.5, (
        "Berdasarkan Tabel 4.9, model YOLOv8-Small menghasilkan nilai mAP@50 sebesar 0,84 dengan latensi "
        "sebesar 12,4 ms. Model YOLOv8-Medium mencatatkan tingkat akurasi tertinggi dengan mAP@50 sebesar 0,89 "
        "dan mAP@50-95 sebesar 0,68."
    ))
    pdf9.output(os.path.join(target_dir, "DOC-JURNAL-AI-09_Deteksi_Objek_Vision.pdf"))

    # 10. Dokumen Kontrol 100% Bersih (True Negative)
    pdf10 = AcademicPdf("Publikasi: Validasi Eksperimen Terkendali")
    pdf10.add_page()
    pdf10.set_font("Helvetica", "B", 13)
    pdf10.cell(0, 8, "HASIL DAN PEMBAHASAN EKSPERIMEN", 0, 1, "C")
    pdf10.ln(2)
    pdf10.set_font("Helvetica", "B", 11)
    pdf10.cell(0, 6, "Hasil Pengujian Akurasi Klasifikasi Multikelas", 0, 1, "L")
    pdf10.set_font("Helvetica", "", 10)
    pdf10.multi_cell(0, 5.5, (
        "Eksperimen klasifikasi multikelas pada 100 sampel uji independen menghasilkan matriks evaluasi "
        "yang sepenuhnya konsisten antar-kolom metrik dan narasi kesimpulan."
    ))
    pdf10.ln(3)
    pdf10.draw_3line_table(
        "Tabel 1 Evaluasi Kinerja Klasifikasi Multikelas Terverifikasi",
        ["Kelas", "Presisi", "Recall", "F1-Score", "Jumlah Sampel"],
        [
            ["Kelas A", "0,92", "0,90", "0,91", "30"],
            ["Kelas B", "0,88", "0,85", "0,86", "35"],
            ["Kelas C", "0,95", "0,94", "0,95", "35"]
        ],
        [40, 35, 35, 35, 35]
    )
    pdf10.set_font("Helvetica", "", 10)
    # 100% CLEAN CONTROL
    pdf10.multi_cell(0, 5.5, (
        "Berdasarkan Tabel 1, Kelas A memperoleh nilai presisi 0,92, recall 0,90, dan F1-Score 0,91 "
        "pada 30 sampel. Kelas C mencatatkan performa klasifikasi tertinggi dengan presisi 0,95 dan recall 0,94. "
        "Seluruh hasil pengujian berada dalam rentang toleransi validitas ilmiah tanpa inkonsistensi numerik."
    ))
    pdf10.output(os.path.join(target_dir, "DOC-KONTROL-10_Naskah_Bebas_Galat_100.pdf"))

    print(f"Berhasil menghasilkan 10 naskah PDF akademik baru di: {target_dir}")

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uploads")
    generate_all_expanded_pdfs(out_dir)
