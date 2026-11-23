"""
Helper script to generate the 3 Golden Preset PDFs for LOCUS.
Uses fpdf2 (installed) to produce clean, realistic thesis/journal draft pages.
"""

import os
from fpdf import FPDF


class PresetPdf(FPDF):
    def header(self):
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, "LOCUS Academic Audit Benchmark Dataset -- Draft Publikasi Ilmiah", 0, 1, "R")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Halaman {self.page_no()}", 0, 0, "C")


def create_preset_1(output_path: str):
    pdf = PresetPdf()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 10, "BAB IV: HASIL DAN PEMBAHASAN", 0, 1, "C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "4.3 Evaluasi Kinerja Model Prediksi", 0, 1, "L")

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, (
        "Berdasarkan pengujian komparatif terhadap dataset uji, metrik evaluasi Root Mean Squared Error (RMSE), "
        "Mean Absolute Error (MAE), dan Akurasi dari ketiga algoritma pembelajaran mesin disajikan pada Tabel 4.3 berikut:"
    ))
    pdf.ln(4)

    # Table 4.3 (3-line scientific table)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Tabel 4.3 Perbandingan Performa Model Prediksi", 0, 1, "L")

    # Table Top Line
    pdf.set_line_width(0.6)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())

    # Header Row
    pdf.set_font("Helvetica", "B", 9)
    col_w = [50, 40, 40, 50]
    headers = ["Model Algoritma", "RMSE", "MAE", "Akurasi"]
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 8, h, 0, 0, "C" if i > 0 else "L")
    pdf.ln(8)

    # Sub-header Line
    pdf.set_line_width(0.3)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())

    # Data Rows
    pdf.set_font("Helvetica", "", 9)
    rows = [
        ["Random Forest", "0,92", "0,78", "0,84"],
        ["XGBoost", "0,41", "0,35", "0,91"],
        ["Support Vector Machine", "0,57", "0,49", "0,86"]
    ]
    for r in rows:
        for i, val in enumerate(r):
            pdf.cell(col_w[i], 7, val, 0, 0, "C" if i > 0 else "L")
        pdf.ln(7)

    # Bottom Line
    pdf.set_line_width(0.6)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())
    pdf.ln(6)

    # Narration Claim with Polarity Error
    pdf.set_font("Helvetica", "", 10)
    claim_text = (
        "Berdasarkan Tabel 4.3 di atas, Model Random Forest memiliki kinerja prediksi terbaik "
        "karena menghasilkan nilai RMSE tertinggi sebesar 0,92 dibandingkan model lainnya. "
        "Hasil ini membuktikan bahwa arsitektur ensemble pohon keputusan mampu meminimalkan galat estimasi secara optimal."
    )
    pdf.multi_cell(0, 6, claim_text)
    pdf.output(output_path)


def create_preset_2(output_path: str):
    pdf = PresetPdf()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "BAB IV: ANALISIS DATA PENELITIAN", 0, 1, "C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "4.2 Uji Prasyarat Analisis Data", 0, 1, "L")

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, (
        "Sebelum dilakukan pengujian hipotesis regresi linear, dilakukan uji normalitas data untuk memenuhi asumsi klasik. "
        "Uji normalitas dilakukan menggunakan uji Kolmogorov-Smirnov dan Shapiro-Wilk pada taraf signifikansi alpha = 0,05."
    ))
    pdf.ln(4)

    # Table 4.1
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Tabel 4.1 Hasil Uji Normalitas Kolmogorov-Smirnov dan Shapiro-Wilk", 0, 1, "L")

    pdf.set_line_width(0.6)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())

    pdf.set_font("Helvetica", "B", 9)
    col_w = [60, 60, 60]
    headers = ["Variabel Penelitian", "Kolmogorov-Smirnov (Sig.)", "Shapiro-Wilk (Sig.)"]
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 8, h, 0, 0, "C" if i > 0 else "L")
    pdf.ln(8)

    pdf.set_line_width(0.3)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())

    pdf.set_font("Helvetica", "", 9)
    rows = [
        ["Kecemasan Akademik (Y)", "0,018", "0,012"],
        ["Efikasi Diri (X)", "0,064", "0,071"]
    ]
    for r in rows:
        for i, val in enumerate(r):
            pdf.cell(col_w[i], 7, val, 0, 0, "C" if i > 0 else "L")
        pdf.ln(7)

    pdf.set_line_width(0.6)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())
    pdf.ln(6)

    # Claim with Inversion error
    pdf.set_font("Helvetica", "", 10)
    claim_text = (
        "Sebagaimana tertera pada Tabel 4.1, data penelitian berdistribusi normal karena nilai Sig. "
        "pada uji Kolmogorov-Smirnov untuk variabel Kecemasan Akademik diperoleh sebesar 0,018 < 0,05. "
        "Oleh karena itu, pengujian statistik parametrik dapat dilanjutkan tanpa transformasi data."
    )
    pdf.multi_cell(0, 6, claim_text)
    pdf.output(output_path)


def create_preset_3(output_path: str):
    pdf = PresetPdf()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "BAB IV: HASIL EKSPERIMEN DAN PEMBAHASAN", 0, 1, "C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "4.4 Pengujian Hipotesis Efektivitas Pembelajaran", 0, 1, "L")

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, (
        "Untuk menguji signifikansi perbedaan peningkatan kemampuan siswa antara kelompok kontrol dan eksperimen, "
        "dilakukan uji Independent Sample t-test dengan derajat bebas df = 58."
    ))
    pdf.ln(4)

    # Table 4.5
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Tabel 4.5 Hasil Uji-t Perbedaan Skor Kelompok Kontrol dan Eksperimen", 0, 1, "L")

    pdf.set_line_width(0.6)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())

    pdf.set_font("Helvetica", "B", 9)
    col_w = [45, 25, 35, 35, 40]
    headers = ["Kelompok", "N", "Rata-rata Pretest", "Rata-rata Posttest", "Uji-t (df=58)"]
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 8, h, 0, 0, "C" if i > 0 else "L")
    pdf.ln(8)

    pdf.set_line_width(0.3)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())

    pdf.set_font("Helvetica", "", 9)
    rows = [
        ["Kelompok Kontrol", "30", "65,40", "68,20", "t = 1,12 (p = 0,267)"],
        ["Kelompok Eksperimen", "30", "64,80", "78,50", "t = 2,41 (p = 0,002)"]
    ]
    for r in rows:
        for i, val in enumerate(r):
            pdf.cell(col_w[i], 7, val, 0, 0, "C" if i > 0 else "L")
        pdf.ln(7)

    pdf.set_line_width(0.6)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())
    pdf.ln(6)

    # Claim with Statcheck inconsistency
    pdf.set_font("Helvetica", "", 10)
    claim_text = (
        "Berdasarkan Tabel 4.5, penerapan media pembelajaran inovatif berpengaruh signifikan "
        "terhadap hasil belajar siswa dengan nilai t(58) = 2,41 dan nilai signifikansi p = 0,002. "
        "Peningkatan ini membuktikan hipotesis tindakan diterima secara meyakinkan."
    )
    pdf.multi_cell(0, 6, claim_text)
    pdf.output(output_path)


if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out_dir, exist_ok=True)
    create_preset_1(os.path.join(out_dir, "preset_1_ml_polarity.pdf"))
    create_preset_2(os.path.join(out_dir, "preset_2_normality_inversion.pdf"))
    create_preset_3(os.path.join(out_dir, "preset_3_statcheck_grim.pdf"))
    print("Presets created successfully.")
