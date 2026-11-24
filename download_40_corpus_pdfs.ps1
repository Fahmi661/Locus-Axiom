# ==============================================================================
# LOCUS Axiom 3.6 - Pengunduh Otomatis 40 Naskah Publik Anonim (6 Disiplin)
# Jalankan di PowerShell dari folder root proyek: D:\HackVidia\Locus
#   powershell -ExecutionPolicy Bypass -File .\download_40_corpus_pdfs.ps1
# Lalu jalankan benchmark korpus:
#   python tests/benchmark_uploaded_corpus.py
# ==============================================================================

$OutDir = Join-Path (Get-Location) "data\uploads"
if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

$Items = @(
    # --- 1. Akuntansi & Keuangan (SPSS Deskriptif, ROA/CAR/NPL) ---
    @{ Name = "S01_Akuntansi_Perbankan_SPSS.pdf"; Url = "https://eskripsi.usm.ac.id/files/skripsi/B21A/2013/B.231.13.0418/B.231.13.0418-07-BAB-IV-20180105010031-FAKTOR-FAKTOR-YANG-MEMPENGARUHI-NILAI-PERUSAHAAN-PADA-SEKTOR-PERBANKAN-YANG--TERDAFTAR-DI-BEI-TAHUN-2012-2015-.pdf" }
    @{ Name = "S02_Akuntansi_ROA_SPSS.pdf"; Url = "https://eskripsi.usm.ac.id/files/skripsi/B21A/2015/B.231.15.0047/B.231.15.0047-07-BAB-IV-20190904032447.pdf" }
    @{ Name = "S03_Akuntansi_Deskriptif_ROA.pdf"; Url = "https://repo.uinsatu.ac.id/11912/7/BAB%20IV.pdf" }
    @{ Name = "S04_Akuntansi_Statistik_SPSS.pdf"; Url = "https://repository.unika.ac.id/16520/5/12.60.0263%20BENU%20PANDUBRATA%20JUDASUBRATA%20IV.pdf" }
    @{ Name = "S05_Akuntansi_GCG_ROE_SPSS.pdf"; Url = "https://eprints.ums.ac.id/68752/6/06.%20bab%204.pdf" }
    @{ Name = "S06_Akuntansi_Reliabilitas_SPSS.pdf"; Url = "https://eprints.ums.ac.id/19942/8/7._BAB_IV.pdf" }
    @{ Name = "S07_Akuntansi_Regresi_UjiT.pdf"; Url = "https://eskripsi.usm.ac.id/files/skripsi/B21A/2015/B.211.15.0136/B.211.15.0136-07-BAB-IV-20190221035400.pdf" }

    # --- 2. Manajemen, Pemasaran & Skala Likert ---
    @{ Name = "S08_Manajemen_Likert_SPSS.pdf"; Url = "https://repositori.buddhidharma.ac.id/2549/3/bab4.pdf" }
    @{ Name = "S09_Manajemen_Promosi_Likert.pdf"; Url = "https://repository.ub.ac.id/100255/6/4._Hasil_dan_Pembahasan.pdf" }
    @{ Name = "S10_Manajemen_Kinerja_Likert.pdf"; Url = "https://eprints.walisongo.ac.id/24824/1/1905036068_YogiSetiawan_Skripsifull%20-%20Yogi%20Setiawan.pdf" }

    # --- 3. Ekonomi & Asumsi Klasik (VIF, Durbin-Watson, Glejser, Uji F) ---
    @{ Name = "S11_Ekonomi_AsumsiKlasik_DW.pdf"; Url = "https://idr.uin-antasari.ac.id/id/eprint/15812/7/BAB%20IV.pdf" }
    @{ Name = "S12_Ekonomi_Multikolinearitas_VIF.pdf"; Url = "https://eskripsi.usm.ac.id/files/skripsi/B21A/2021/B.231.21.0045/B.231.21.0045-07-BAB-IV-20250106110541.pdf" }
    @{ Name = "S13_Ekonomi_Regresi_UjiF.pdf"; Url = "https://repository.dinamika.ac.id/id/eprint/2320/6/BAB_IV.pdf" }
    @{ Name = "S14_Ekonomi_Profitabilitas_DW.pdf"; Url = "https://eskripsi.usm.ac.id/files/skripsi/B21A/2015/B.211.15.0234/B.211.15.0234-07-BAB-IV-20190823122156.pdf" }

    # --- 4. Informatika & Machine Learning (Confusion Matrix, Precision, Recall, F1) ---
    @{ Name = "S15_ML_Klasifikasi_F1.pdf"; Url = "https://journal.untar.ac.id/index.php/JKI/article/view/35638/21549" }
    @{ Name = "S16_ML_Sentimen_ConfusionMatrix.pdf"; Url = "https://ejournal.ust.ac.id/index.php/JTIUST/article/view/3878/2981" }
    @{ Name = "S17_ML_DigitalTI_F1Score.pdf"; Url = "https://jurnal.um-palembang.ac.id/digital/article/download/9429/pdf" }
    @{ Name = "S18_ML_Sentimen_JATI.pdf"; Url = "https://www.ejournal.itn.ac.id/jati/article/download/11774/6636/" }
    @{ Name = "S19_ML_KomparasiMetode_JATI.pdf"; Url = "https://ejournal.itn.ac.id/index.php/jati/article/download/5238/3377" }
    @{ Name = "S20_ML_KualitasUdara_ANN_SVM.pdf"; Url = "https://journal.untar.ac.id/index.php/JKI/article/view/34589/20671" }
    @{ Name = "S21_ML_EvaluasiModel_JTT.pdf"; Url = "https://journal.nurulfikri.ac.id/index.php/JTT/article/download/605/304" }
    @{ Name = "S22_ML_F1Score_JATI.pdf"; Url = "https://ejournal.itn.ac.id/index.php/jati/article/download/7026/4233" }
    @{ Name = "S23_ML_CNN_Transmisi_UNDIP.pdf"; Url = "https://ejournal.undip.ac.id/index.php/transmisi/article/download/67355/pdf" }
    @{ Name = "S24_ML_AlexNet_Polines.pdf"; Url = "https://jurnal.polines.ac.id/index.php/rekayasa/article/download/7170/110124" }
    @{ Name = "S25_ML_Phishing_Transmisi_UNDIP.pdf"; Url = "https://ejournal.undip.ac.id/index.php/transmisi/article/download/64749/pdf" }
    @{ Name = "S26_ML_SVM_JSINBIS_UNDIP.pdf"; Url = "https://ejournal.undip.ac.id/index.php/jsinbis/article/download/50136/pdf" }
    @{ Name = "S27_ML_Stroke_JMASIF_UNDIP.pdf"; Url = "https://ejournal.undip.ac.id/index.php/jmasif/article/download/78464/30204" }

    # --- 5. Kesehatan, Biomedis & Keperawatan (Uji t, Mann-Whitney, Wilcoxon, Chi-Square) ---
    @{ Name = "S28_Kesehatan_Literasi_SPSS.pdf"; Url = "http://repo.poltekkestasikmalaya.ac.id/5989/8/BAB%20IV%20HASIL%20DAN%20PEMBAHASAN..pdf" }
    @{ Name = "S29_Kesehatan_Keperawatan_KMB.pdf"; Url = "https://repository.poltekkes-denpasar.ac.id/1317/3/BAB%20IV.pdf" }
    @{ Name = "S30_Kesehatan_MannWhitney_PairedT.pdf"; Url = "https://eprints.poltekkesjogja.ac.id/18118/5/5.%20BAB%20IV.pdf" }
    @{ Name = "S31_Kesehatan_MannWhitney_PVal.pdf"; Url = "https://eprints.poltekkesjogja.ac.id/2289/5/BAB%20IV.pdf" }
    @{ Name = "S32_Kesehatan_DietDASH_Wilcoxon.pdf"; Url = "https://eprints.poltekkesjogja.ac.id/16296/7/Chapter%204.pdf" }
    @{ Name = "S33_Kesehatan_Wilcoxon_MannWhitney.pdf"; Url = "https://eprints.poltekkesjogja.ac.id/13389/5/BAB%20IV.pdf" }
    @{ Name = "S34_Kesehatan_Korelasi_Kendall.pdf"; Url = "https://eprints.poltekkesjogja.ac.id/8208/8/Chapter%204.doc.pdf" }
    @{ Name = "S35_Kesehatan_TumbuhKembang.pdf"; Url = "https://eprints.poltekkesjogja.ac.id/2181/5/BAB%20IV.pdf" }

    # --- 6. Pendidikan & Psikologi (Kolmogorov-Smirnov, Levene, Pretest-Posttest, N-Gain) ---
    @{ Name = "S36_Pendidikan_PrePost_SPSS.pdf"; Url = "https://repo.uinsatu.ac.id/21816/7/BAB%20IV.pdf" }
    @{ Name = "S37_Pendidikan_Eksperimen_UNY.pdf"; Url = "https://eprints.uny.ac.id/67148/6/6.%20BAB%20IV.pdf" }
    @{ Name = "S38_Pendidikan_Normalitas_Homogenitas_UNY.pdf"; Url = "https://eprints.uny.ac.id/18570/6/5.%20BAB%20IV.pdf" }
    @{ Name = "S39_Pendidikan_KS_Homogenitas_UNY.pdf"; Url = "https://eprints.uny.ac.id/63658/6/5.%20File%20BAB%20IV.pdf" }
    @{ Name = "S40_Pendidikan_UjiAsumsi_UNY.pdf"; Url = "http://eprints.uny.ac.id/66685/5/BAB%20IV.pdf" }
)

$ok = 0
$fail = 0
$total = $Items.Count

Write-Host "======================================================================"
Write-Host "Mengunduh $total Naskah Publik Anonim (6 Disiplin) ke: $OutDir"
Write-Host "======================================================================"

for ($i = 0; $i -lt $total; $i++) {
    $item = $Items[$i]
    $dest = Join-Path $OutDir $item.Name
    $idxStr = "{0:D2}/{1:D2}" -f ($i + 1), $total

    if (Test-Path $dest) {
        Write-Host "[$idxStr] SKIP (sudah ada): $($item.Name)"
        $ok++
        continue
    }

    & curl.exe -L -s -k --max-time 25 --fail -A "Mozilla/5.0" -o $dest $item.Url
    if ($LASTEXITCODE -eq 0 -and (Test-Path $dest)) {
        $bytes = [System.IO.File]::ReadAllBytes($dest)
        if ($bytes.Length -ge 4 -and [System.Text.Encoding]::ASCII.GetString($bytes, 0, 4) -eq "%PDF") {
            $kb = [math]::Round($bytes.Length / 1024, 1)
            Write-Host "[$idxStr] OK ($kb KB): $($item.Name)" -ForegroundColor Green
            $ok++
        } else {
            Remove-Item $dest -Force -ErrorAction SilentlyContinue
            Write-Host "[$idxStr] GAGAL (bukan PDF valid): $($item.Name)" -ForegroundColor Yellow
            $fail++
        }
    } else {
        Remove-Item $dest -Force -ErrorAction SilentlyContinue
        Write-Host "[$idxStr] GAGAL (timeout/server kampus): $($item.Name)" -ForegroundColor Red
        $fail++
    }
}

Write-Host "======================================================================"
Write-Host "Selesai! Berhasil: $ok | Gagal: $fail"
Write-Host "Sekarang jalankan: python tests/benchmark_uploaded_corpus.py"
Write-Host "======================================================================"
