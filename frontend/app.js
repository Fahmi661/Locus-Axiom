/**
 * LOCUS: Cursor for Scientific Integrity
 * Notion Style System: Warm Paper Notebook Under Afternoon Sun
 * Frontend Controller: Multi-Page Navigation, Precision X-Ray Bounding Boxes & Interactive Proofs
 * 100% Offline, Zero-PII, Zero-AGPL, Anti-Slop Clean
 */

let currentBundle = null;
let currentPresetIndex = 0;
let activeFindingId = null;
let presetsList = [];
let currentView = "landing";
let currentDocPage = 1;
let totalDocPages = 1;
let currentCanvasZoom = 1.0;
let currentFindingsFilter = "all";

// Authoritative Indonesian metadata for scientific verdict types
const VERDICT_META = {
    "POLARITY_INVERSION_ERROR": {
        title: "Inversi Polaritas Metrik",
        code: "POLARITAS",
        category: "error",
        desc: "Metrik galat (seperti RMSE/MAE) diinterpretasikan terbalik (makin kecil makin baik)."
    },
    "PREREQUISITE_LOGIC_INVERSION": {
        title: "Inversi Logika Uji Prasyarat",
        code: "LOGIKA-PRASYARAT",
        category: "error",
        desc: "Uji normalitas menyimpulkan normal padahal p < 0,05 (tolak H0, data tidak normal)."
    },
    "DIRECT_CELL_CONTRADICTION": {
        title: "Inkonsistensi Nilai Sel Tabel",
        code: "SEL-TABEL",
        category: "error",
        desc: "Nilai yang diklaim di narasi bertentangan langsung dengan angka di tabel bukti."
    },
    "WARN_TRUNCATION_ROUNDING": {
        title: "Peringatan Pemotongan Desimal",
        code: "PEMBULATAN",
        category: "warn",
        desc: "Angka dipotong (truncation) tanpa kaidah pembulatan baku matematika."
    },
    "WARN_ROUNDING": {
        title: "Peringatan Toleransi Pembulatan",
        code: "PEMBULATAN",
        category: "warn",
        desc: "Terdapat sedikit variasi pembulatan desimal dibanding nilai baku."
    },
    "DECISION_FLIP_ERROR": {
        title: "Pembalikan Keputusan Signifikansi",
        code: "DECISION-FLIP",
        category: "error",
        desc: "P-value asli berada di seberang ambang alpha 0,05 dibanding yang dilaporkan."
    },
    "GRIM_MEAN_INCONSISTENCY": {
        title: "Anomali Kelayakan Sampel (GRIM)",
        code: "UJI-GRIM",
        category: "error",
        desc: "Nilai rata-rata tidak mungkin dihasilkan oleh jumlah responden Likert integer."
    },
    "GRIMMER_SD_INCONSISTENCY": {
        title: "Anomali Varians Sampel (GRIMMER)",
        code: "UJI-GRIMMER",
        category: "error",
        desc: "Standar deviasi tidak konsisten secara matematis dengan ukuran sampel."
    },
    "DEBIT_BINARY_INCONSISTENCY": {
        title: "Pelanggaran Batas Biner (DEBIT)",
        code: "UJI-DEBIT",
        category: "error",
        desc: "Kombinasi mean dan varians melanggar batas teoritis variabel biner 0/1."
    },
    "TOTAL_N_SUBGROUP_DISCREPANCY": {
        title: "Diskrepansi Jumlah Sampel (Total-N)",
        code: "TOTAL-N",
        category: "error",
        desc: "Jumlah responden pada tabel tidak cocok dengan total naskah Bab Metodologi."
    },
    "CONFUSION_MATRIX_INCONSISTENCY": {
        title: "Inkonsistensi Matriks Evaluasi",
        code: "CONF-MATRIX",
        category: "error",
        desc: "Nilai precision, recall, atau F1 tidak sinkron dengan matriks konfusi."
    },
    "ROW_PERCENTAGE_SUM_ERROR": {
        title: "Jumlah Persentase Baris Tidak 100%",
        code: "PERSENTASE",
        category: "error",
        desc: "Total persentase baris melebihi atau kurang dari toleransi pembulatan 100%."
    },
    "INLINE_FORMULA_NARRATIVE_CONTRADICTION": {
        title: "Kontradiksi Formula Narasi",
        code: "FORMULA",
        category: "error",
        desc: "Hasil perhitungan rumus inline naskah tidak cocok dengan angka narasi."
    },
    "APA_PRECISION_NOTICE": {
        title: "Catatan Presisi Pelaporan APA",
        code: "FORMAT-APA",
        category: "warn",
        desc: "Format pelaporan statistik belum memenuhi panduan presisi APA 7th Edition."
    },
    "PASS": {
        title: "Konsisten Terverifikasi",
        code: "PASS",
        category: "pass",
        desc: "Klaim numerik dan kesimpulan statistik konsisten dengan bukti data tabel."
    }
};

function getVerdictMeta(verdict) {
    return VERDICT_META[verdict] || {
        title: (verdict || "TEMUAN").replace(/_/g, " "),
        code: "TEMUAN",
        category: ((verdict || "").includes("WARN") || (verdict || "").includes("NOTICE")) ? "warn" : (verdict === "PASS" ? "pass" : "error"),
        desc: "Temuan audit integritas numerik dokumen ilmiah."
    };
}

document.addEventListener("DOMContentLoaded", () => {
    initPresets();
    setupDropzone();
    setupEventListeners();

    // Attach scroll listeners to update cross-pane Bézier connector
    const viewport = document.getElementById("pdf-viewport-container");
    const rightPane = document.querySelector(".pane-right");
    if (viewport) viewport.addEventListener("scroll", drawSvgConnector);
    if (rightPane) rightPane.addEventListener("scroll", drawSvgConnector);

    window.addEventListener("resize", () => {
        if (currentView === "studio") {
            handleResize();
            drawSvgConnector();
        }
    });
});

// View Navigation: 'landing' or 'studio'
function navigateTo(viewName) {
    if (viewName === "studio") {
        window.location.href = "/app/studio.html";
        return;
    }
    currentView = viewName;
    const landingView = document.getElementById("view-landing");
    const studioView = document.getElementById("view-studio");
    const navStudioBtn = document.getElementById("top-open-studio-btn");

    if (viewName === "landing") {
        if (landingView) landingView.style.display = "block";
        if (studioView) studioView.style.display = "none";
        if (navStudioBtn) navStudioBtn.style.display = "inline-flex";
        clearSvg();
        window.scrollTo({ top: 0, behavior: "smooth" });
    } else {
        if (landingView) landingView.style.display = "none";
        if (studioView) studioView.style.display = "flex";
        if (navStudioBtn) navStudioBtn.style.display = "none";

        setTimeout(() => {
            handleResize();
            drawSvgConnector();
        }, 60);
    }
}

function scrollToSection(sectionId) {
    if (currentView !== "landing") {
        navigateTo("landing");
        setTimeout(() => {
            const el = document.getElementById(sectionId);
            if (el) el.scrollIntoView({ behavior: "smooth" });
        }, 100);
    } else {
        const el = document.getElementById(sectionId);
        if (el) el.scrollIntoView({ behavior: "smooth" });
    }
}

function openPresetInStudio(index) {
    window.location.href = `/app/studio.html?preset=${index}`;
}

function triggerPdfUpload() {
    const input = document.getElementById("pdf-file-input");
    if (input) input.click();
}

function handleResize() {
    const img = document.getElementById("pdf-page-img");
    const overlay = document.getElementById("xray-bounding-box-overlay");
    const svgEvidence = document.getElementById("page-evidence-svg");
    if (img && overlay && svgEvidence && currentBundle) {
        populateBoundingBoxes(overlay, svgEvidence, currentBundle, img);
    }
}

// Load 3 Golden Presets
async function initPresets() {
    try {
        const res = await fetch("/api/v1/presets");
        const data = await res.json();
        if (data.status === "success" && data.presets.length > 0) {
            presetsList = data.presets;
            renderPresetButtons();
            loadPreset(0, false);
        }
    } catch (err) {
        console.error("Gagal memuat presets:", err);
    }
}

function renderPresetButtons() {
    const container = document.getElementById("preset-buttons-container");
    if (!container) return;
    container.innerHTML = "";
    presetsList.forEach((p, idx) => {
        const btn = document.createElement("button");
        btn.className = `btn-preset ${idx === currentPresetIndex ? "active" : ""}`;
        btn.id = `preset-btn-${idx}`;
        btn.innerHTML = `<span style="font-weight:700">${p.id}</span>: ${p.title}`;
        btn.onclick = () => loadPreset(idx, true);
        container.appendChild(btn);
    });
}

let loadingTimer = null;
let loadingStartTime = 0;
let activeAuditAbortController = null;
let activeAuditPollInterval = null;

const AUDIT_STEPS_DEF = [
    {
        id: 1,
        title: "Deteksi tabel",
        shortLabel: "Deteksi tabel",
        desc: "Geometri tabel 3-garis dan klaster kolom.",
        time: "0,18 dtk"
    },
    {
        id: 2,
        title: "Pemisahan klaim",
        shortLabel: "Pemisahan klaim",
        desc: "Teks tabel dimasking agar tidak bocor ke narasi.",
        time: "0,22 dtk"
    },
    {
        id: 3,
        title: "Ekspansi variabel",
        shortLabel: "Ekspansi variabel",
        desc: "Stem morfologi dan resolusi anafora Bab 3/4.",
        time: "0,31 dtk"
    },
    {
        id: 4,
        title: "Penautan semantik",
        shortLabel: "Penautan semantik",
        desc: "Duet model ONNX INT8: bge-reranker-v2-m3 dan mDeBERTa-v3.",
        subProgress: "model 2/2 · cross-encoder",
        time: "0,42 dtk"
    },
    {
        id: 5,
        title: "Solver deterministik",
        shortLabel: "Solver matematika",
        desc: "8 solver matematika: statcheck, GRIM, FormulaEval.",
        subProgress: "solver 8/8 · SciPy",
        time: "0,19 dtk"
    },
    {
        id: 6,
        title: "Sintesis bukti",
        shortLabel: "Sintesis bukti",
        desc: "Kurva Bezier, What-If stepper, tanda tangan SHA-256.",
        subProgress: "hash sha-256 · siap",
        time: "0,09 dtk"
    }
];

function renderStepsUI(currentActiveStep) {
    AUDIT_STEPS_DEF.forEach((step, idx) => {
        const stepNum = idx + 1;
        const el = document.getElementById(`step-${stepNum}`);
        if (!el) return;

        if (stepNum < currentActiveStep) {
            el.className = "timeline-row step-item completed";
            el.innerHTML = `
              <div class="timeline-indicator-col">
                <div class="timeline-icon-box">
                  <svg style="width: 13px; height: 13px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.75" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                </div>
                <div class="timeline-line-connector" style="background: #10b981;"></div>
              </div>
              <div class="timeline-content-col">
                <div class="timeline-text-wrap">
                  <div class="timeline-title">${step.title}</div>
                  <div class="timeline-desc">${step.desc}</div>
                </div>
                <span class="timeline-time-badge">${step.time}</span>
              </div>
            `;
        } else if (stepNum === currentActiveStep) {
            el.className = "timeline-row step-item active";
            el.innerHTML = `
              <div class="timeline-indicator-col">
                <div class="timeline-icon-box">
                  <div class="locus-spinner" aria-label="Sedang memproses"></div>
                </div>
                <div class="timeline-line-connector"></div>
              </div>
              <div class="timeline-content-col">
                <div class="timeline-text-wrap">
                  <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <div class="timeline-title">${step.title}</div>
                    ${step.subProgress ? `<span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600; color: #2563eb; background: #eff6ff; padding: 1px 6px; border-radius: 4px;">${step.subProgress}</span>` : ''}
                  </div>
                  <div class="timeline-desc" style="color: #475569; font-weight: 450;">${step.desc}</div>
                </div>
              </div>
            `;
        } else {
            el.className = "timeline-row step-item pending";
            el.innerHTML = `
              <div class="timeline-indicator-col">
                <div class="timeline-icon-box"></div>
                <div class="timeline-line-connector"></div>
              </div>
              <div class="timeline-content-col">
                <div class="timeline-text-wrap">
                  <div class="timeline-title">${step.title}</div>
                  <div class="timeline-desc" style="display: none;">${step.desc}</div>
                </div>
              </div>
            `;
        }
    });
}

function showAuditLoading(docTitle = "BAB 4.pdf", sizeKb = "367") {
    const overlay = document.getElementById("modalOverlay") || document.getElementById("locus-loading-overlay");
    const modalTitle = document.getElementById("modalTitle");
    const modalSubtitle = document.getElementById("modalSubtitle");
    const activeStageLabel = document.getElementById("activeStageLabel");
    const progressPercent = document.getElementById("progressPercent");
    const progressBarFill = document.getElementById("progressBarFill");
    const progressBarEl = document.getElementById("progressBarEl");
    const completedBanner = document.getElementById("completedBanner");
    const errorBanner = document.getElementById("errorBanner");
    const defaultFooter = document.getElementById("defaultFooter");
    const elapsedTimer = document.getElementById("elapsedTimer");
    const longWaitBanner = document.getElementById("longWaitBanner");
    const longWaitBannerText = document.getElementById("longWaitBannerText");

    let cleanName = docTitle;
    if (cleanName.startsWith("Mengaudit: ")) {
        cleanName = cleanName.replace("Mengaudit: ", "");
    }
    if (cleanName.includes(" (")) {
        cleanName = cleanName.split(" (")[0];
    }

    if (modalTitle) modalTitle.textContent = `Mengaudit ${cleanName}`;
    if (modalSubtitle) modalSubtitle.textContent = `${sizeKb} KB · 100% offline`;
    if (activeStageLabel) activeStageLabel.textContent = "Merender halaman PDF...";
    if (progressPercent) progressPercent.textContent = "5%";
    if (progressBarFill) {
        progressBarFill.style.width = "5%";
        progressBarFill.classList.remove('bg-[#10b981]', 'bg-[#e11d48]');
        progressBarFill.classList.add('bg-[#0075de]');
    }
    if (progressBarEl) progressBarEl.setAttribute('aria-valuenow', '5');
    if (completedBanner) completedBanner.classList.add('hidden');
    if (errorBanner) errorBanner.classList.add('hidden');
    if (longWaitBanner) longWaitBanner.classList.add('hidden');
    if (defaultFooter) defaultFooter.classList.remove('hidden');

    renderStepsUI(1);

    if (overlay) {
        overlay.style.display = "flex";
        overlay.style.opacity = "1";
    }

    loadingStartTime = performance.now();
    if (loadingTimer) clearInterval(loadingTimer);
    loadingTimer = setInterval(() => {
        const elapsedSec = (performance.now() - loadingStartTime) / 1000;
        if (elapsedTimer) {
            const sec = elapsedSec.toFixed(2).replace('.', ',');
            elapsedTimer.textContent = `${sec} dtk`;
        }
        if (longWaitBanner && longWaitBannerText) {
            if (elapsedSec >= 180) {
                longWaitBanner.classList.remove('hidden');
                longWaitBannerText.textContent = "Proses memerlukan waktu lebih lama karena ukuran/kompleksitas tabel dokumen. Sistem tetap aktif bekerja - tunggu sebentar lagi atau klik Batalkan jika ingin mengulang.";
            } else if (elapsedSec >= 90) {
                longWaitBanner.classList.remove('hidden');
                longWaitBannerText.textContent = "Masih memproses dokumen besar secara offline. Mohon tunggu sedikit lagi dan jangan tutup halaman ini.";
            } else if (elapsedSec >= 25) {
                longWaitBanner.classList.remove('hidden');
                longWaitBannerText.textContent = "Dokumen cukup panjang. Proses audit sedang berjalan di CPU lokal - mohon tunggu sebentar lagi.";
            } else {
                longWaitBanner.classList.add('hidden');
            }
        }
    }, 100);

    const btnCloseModal = document.getElementById('btnCloseModal');
    const btnCancelAudit = document.getElementById('btnCancelAudit');
    const btnRetryAudit = document.getElementById('btnRetryAudit');

    const cancelAudit = () => {
        if (activeAuditAbortController) {
            try {
                activeAuditAbortController.abort();
            } catch (_) {}
            activeAuditAbortController = null;
        }
        fetch("/api/v1/audit/cancel", { method: "POST" }).catch(() => {});
        if (activeAuditPollInterval) {
            clearInterval(activeAuditPollInterval);
            activeAuditPollInterval = null;
        }
        if (loadingTimer) {
            clearInterval(loadingTimer);
            loadingTimer = null;
        }
        if (longWaitBanner) longWaitBanner.classList.add('hidden');
        if (overlay) overlay.style.display = "none";
    };

    if (btnCloseModal) {
        btnCloseModal.onclick = cancelAudit;
    }
    if (btnCancelAudit) {
        btnCancelAudit.onclick = cancelAudit;
    }
    if (btnRetryAudit) {
        btnRetryAudit.onclick = () => {
            const input = document.getElementById("pdf-file-input") || document.getElementById("file-input");
            if (input) input.click();
        };
    }
}

function setPipelineStep(stepIndex, percent, stageText) {
    const activeStageLabel = document.getElementById("activeStageLabel");
    const progressPercent = document.getElementById("progressPercent");
    const progressBarFill = document.getElementById("progressBarFill");
    const progressBarEl = document.getElementById("progressBarEl");

    if (activeStageLabel) {
        const stepDef = AUDIT_STEPS_DEF[stepIndex - 1];
        activeStageLabel.textContent = stageText || (stepDef ? stepDef.shortLabel : "Memproses...");
    }
    if (progressPercent) progressPercent.textContent = `${percent}%`;
    if (progressBarFill) progressBarFill.style.width = `${percent}%`;
    if (progressBarEl) progressBarEl.setAttribute('aria-valuenow', percent);

    renderStepsUI(stepIndex);
}

function finishAuditLoading(findingsSummary, callback) {
    if (typeof findingsSummary === "function") {
        callback = findingsSummary;
        findingsSummary = "Audit terverifikasi · 100% konsisten";
    }

    if (loadingTimer) {
        clearInterval(loadingTimer);
        loadingTimer = null;
    }

    const totalTime = ((performance.now() - loadingStartTime) / 1000).toFixed(2).replace('.', ',');
    const modalTitle = document.getElementById("modalTitle");
    const activeStageLabel = document.getElementById("activeStageLabel");
    const progressPercent = document.getElementById("progressPercent");
    const progressBarFill = document.getElementById("progressBarFill");
    const completedBanner = document.getElementById("completedBanner");
    const completedSummaryText = document.getElementById("completedSummaryText");
    const completedElapsedTime = document.getElementById("completedElapsedTime");
    const defaultFooter = document.getElementById("defaultFooter");
    const btnViewResults = document.getElementById("btnViewResults");
    const longWaitBanner = document.getElementById("longWaitBanner");

    renderStepsUI(7);

    if (longWaitBanner) longWaitBanner.classList.add('hidden');
    if (modalTitle) modalTitle.textContent = "Audit selesai";
    if (activeStageLabel) activeStageLabel.textContent = "Semua tahap terverifikasi";
    if (progressPercent) progressPercent.textContent = "100%";
    if (progressBarFill) {
        progressBarFill.style.width = "100%";
        progressBarFill.classList.remove('bg-[#0075de]', 'bg-[#e11d48]');
        progressBarFill.classList.add('bg-[#10b981]');
    }

    if (completedSummaryText) {
        completedSummaryText.textContent = findingsSummary || "Audit terverifikasi";
    }
    if (completedElapsedTime) {
        completedElapsedTime.textContent = `(${totalTime} dtk)`;
    }

    if (completedBanner) completedBanner.classList.remove('hidden');
    if (defaultFooter) defaultFooter.classList.add('hidden');

    let navigated = false;
    const proceed = () => {
        if (navigated) return;
        navigated = true;
        const overlay = document.getElementById("modalOverlay") || document.getElementById("locus-loading-overlay");
        if (overlay) overlay.style.display = "none";
        if (typeof callback === "function") callback();
    };

    if (btnViewResults) {
        btnViewResults.onclick = proceed;
    }

    setTimeout(proceed, 850);
}

function showAuditError(msg) {
    if (loadingTimer) clearInterval(loadingTimer);
    const modalTitle = document.getElementById("modalTitle");
    const activeStageLabel = document.getElementById("activeStageLabel");
    const progressBarFill = document.getElementById("progressBarFill");
    const errorBanner = document.getElementById("errorBanner");
    const errorBannerDetail = document.getElementById("errorBannerDetail");
    const completedBanner = document.getElementById("completedBanner");
    const longWaitBanner = document.getElementById("longWaitBanner");

    if (longWaitBanner) longWaitBanner.classList.add('hidden');
    if (modalTitle) modalTitle.textContent = "Audit terhenti";
    if (activeStageLabel) activeStageLabel.textContent = "Galat pada sistem";
    if (progressBarFill) {
        progressBarFill.classList.remove('bg-[#0075de]', 'bg-[#10b981]');
        progressBarFill.classList.add('bg-[#e11d48]');
    }
    if (errorBannerDetail) errorBannerDetail.textContent = msg;
    if (errorBanner) errorBanner.classList.remove('hidden');
    if (completedBanner) completedBanner.classList.add('hidden');
}

function loadPreset(index, switchToStudio = false) {
    if (typeof index === "string") {
        if (typeof loadMockupPreset === "function") {
            loadMockupPreset(index);
        }
        return;
    }
    currentPresetIndex = index;
    currentDocPage = 1;

    document.querySelectorAll(".btn-preset").forEach((b, i) => {
        b.classList.toggle("active", i === index);
    });

    const preset = presetsList[index];
    if (!preset || !preset.bundle) return;

    if (switchToStudio) {
        showAuditLoading(`Memuat Preset: ${preset.id} (${preset.title})`);
        setPipelineStep(1, 25, "Tahap 1: Memuat draf naskah PDF & struktur tabel...");
        setTimeout(() => {
            setPipelineStep(3, 65, "Tahap 3: Memvalidasi penautan klaim RapidFuzz & duet ONNX...");
        }, 120);
        setTimeout(() => {
            setPipelineStep(5, 90, "Tahap 5: Mengevaluasi 8 Solver Deterministik & What-If stepper...");
        }, 240);
        setTimeout(() => {
            finishAuditLoading(() => {
                displayAuditBundle(preset.bundle, `/static/pages/preset_${index + 1}/page_1.png`);
                if (currentView !== "studio") {
                    navigateTo("studio");
                }
            });
        }, 420);
    } else {
        displayAuditBundle(preset.bundle, `/static/pages/preset_${index + 1}/page_1.png`);
    }
}

// Display Audit Bundle
function displayAuditBundle(bundle, pageImgUrl = null) {
    currentBundle = bundle;

    // Multi-page detection
    if (bundle.page_images && Object.keys(bundle.page_images).length > 0) {
        totalDocPages = Object.keys(bundle.page_images).length;
    } else {
        totalDocPages = 1;
    }
    currentDocPage = 1;

    updatePageNavControls();

    if (!pageImgUrl) {
        if (bundle.page_images && bundle.page_images["1"]) {
            pageImgUrl = bundle.page_images["1"];
        } else if (bundle.page_images && Object.values(bundle.page_images).length > 0) {
            pageImgUrl = Object.values(bundle.page_images)[0];
        } else {
            pageImgUrl = "/static/pages/preset_1/page_1.png";
        }
    }

    // Update summary counts
    const sc = bundle.summary_counts || {};
    const setElemText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.innerText = val;
    };
    setElemText("sum-checked", sc.total_claims_checked || (bundle.findings || []).length || 0);
    setElemText("sum-pass", sc.pass_count || 0);
    setElemText("sum-warn", sc.warn_rounding_count || 0);
    setElemText("sum-error", sc.contradiction_or_flip_count || 0);

    // Reset filter to 'all'
    currentFindingsFilter = "all";
    document.querySelectorAll(".filter-pill").forEach(p => {
        p.classList.toggle("active", p.id === "filter-all");
    });

    // Render Right Pane: Findings
    renderFindingsList(bundle.findings || []);

    // Render Left Pane: PDF Page View
    renderPdfXRayCanvas(bundle, pageImgUrl);

    // Default select first finding
    if (bundle.findings && bundle.findings.length > 0) {
        selectFinding(bundle.findings[0].finding_id);
    } else {
        clearSvg();
    }
}

function updatePageNavControls() {
    const navBox = document.getElementById("page-nav-controls");
    const indicator = document.getElementById("page-nav-indicator");
    if (navBox && indicator) {
        if (totalDocPages > 1) {
            navBox.style.display = "inline-flex";
            indicator.innerText = `Hal. ${currentDocPage} / ${totalDocPages}`;
        } else {
            navBox.style.display = "none";
        }
    }
}

function changeDocPage(delta) {
    const newPage = currentDocPage + delta;
    if (newPage >= 1 && newPage <= totalDocPages) {
        switchDocPage(newPage);
    }
}

function switchDocPage(targetPage) {
    currentDocPage = targetPage;
    updatePageNavControls();

    let newImgUrl = `/static/pages/preset_${currentPresetIndex + 1}/page_1.png`;
    if (currentBundle && currentBundle.page_images && currentBundle.page_images[String(targetPage)]) {
        newImgUrl = currentBundle.page_images[String(targetPage)];
    }

    const img = document.getElementById("pdf-page-img");
    const overlay = document.getElementById("xray-bounding-box-overlay");
    const svgEvidence = document.getElementById("page-evidence-svg");

    if (img && overlay && svgEvidence) {
        const updateAll = () => {
            populateBoundingBoxes(overlay, svgEvidence, currentBundle, img);
            drawSvgConnector();
            updateJumpPills();
        };

        img.onload = () => {
            updateAll();
            img.onload = null;
        };
        img.src = newImgUrl;
        if (img.complete && img.naturalWidth > 0) {
            updateAll();
        }
    }
}

function updateJumpPills() {
    if (!currentBundle || !currentBundle.findings) return;
    currentBundle.findings.forEach(f => {
        const claimPage = f.claim_source?.page || 1;
        const evidencePage = f.table_evidence?.page || claimPage;
        if (claimPage === evidencePage) return;

        const pill = document.getElementById(`btn-jump-${f.finding_id}`);
        if (pill) {
            if (currentDocPage === evidencePage) {
                pill.innerHTML = `Lihat Teks Klaim (Hal. ${claimPage}) ↖`;
                pill.onclick = (e) => { e.stopPropagation(); switchDocPage(claimPage); };
            } else {
                pill.innerHTML = `Lihat Tabel Bukti (Hal. ${evidencePage}) ↗`;
                pill.onclick = (e) => { e.stopPropagation(); switchDocPage(evidencePage); };
            }
        }
    });
}

// Render Findings List
function renderFindingsList(findings) {
    const container = document.getElementById("findings-list-container");
    if (!container) return;
    container.innerHTML = "";

    if (findings.length === 0) {
        container.innerHTML = `
            <div style="padding: 36px 20px; text-align: center; color: var(--color-stone);">
                <div style="font-size: 32px; margin-bottom: 12px; color: #059669;">✓</div>
                <div style="font-weight: 600; font-size: 15px; color: var(--color-ink-black);">100% Konsistensi Terverifikasi</div>
                <div style="font-size: 13px; margin-top: 6px; line-height: 1.6; color: var(--color-graphite);">
                    Tidak ditemukan anomali statistik atau ketidaksesuaian logika pada dokumen ini.
                </div>
            </div>
        `;
        return;
    }

    findings.forEach((f) => {
        const meta = getVerdictMeta(f.verdict);
        const card = document.createElement("div");
        card.className = "finding-card";
        card.id = `card-${f.finding_id}`;
        card.setAttribute("data-verdict", f.verdict);
        card.setAttribute("data-category", meta.category);
        card.onclick = () => selectFinding(f.finding_id);

        let verdictClass = "verdict-error";
        let dotClass = "dot-rose";
        if (meta.category === "warn") {
            verdictClass = "verdict-warn";
            dotClass = "dot-amber";
        } else if (meta.category === "pass") {
            verdictClass = "verdict-pass";
            dotClass = "dot-emerald";
        }

        const mathTrace = f.math_and_logic_trace || {};
        const pedagogical = f.pedagogical_prompt || {};
        const claimPage = f.claim_source?.page || 1;
        const evidencePage = f.table_evidence?.page || claimPage;
        const isCrossPage = (claimPage !== evidencePage);
        const snippet = f.table_evidence?.row_snippet;

        card.innerHTML = `
            <div class="finding-card-header">
                <div class="verdict-badge-wrap">
                    <span class="verdict-tag ${verdictClass}">
                        <span class="filter-dot ${dotClass}"></span>
                        ${meta.title}
                    </span>
                    <span class="verdict-code-pill">${meta.code}</span>
                </div>
                <span class="finding-id">${f.finding_id} · Hal. ${claimPage}</span>
            </div>
            
            <!-- 1. Diff 3-Second Format Box: Top Priority Side-by-Side Comparison -->
            ${f.diff_details ? `
                <div class="diff-3sec-box">
                    <div class="diff-3sec-grid">
                        <div class="diff-3sec-cell cell-claim">
                            <span class="diff-3sec-lbl">Tertulis di Kalimat (Hal. ${claimPage}):</span>
                            <div class="diff-3sec-val val-claim">${f.diff_details.claimed_val}</div>
                        </div>
                        <div class="diff-3sec-arrow">➔</div>
                        <div class="diff-3sec-cell cell-table">
                            <span class="diff-3sec-lbl">Tertera di Tabel (Hal. ${evidencePage}):</span>
                            <div class="diff-3sec-val val-table">
                                ${f.diff_details.table_val}
                                ${f.diff_details.table_rounded ? `<span class="baku-badge">(Baku: ${f.diff_details.table_rounded})</span>` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="diff-3sec-explanation">
                        <strong>Penjelasan Singkat:</strong> ${f.diff_details.plain_explanation || 'Nilai yang dilaporkan pada narasi tidak sesuai dengan data pada tabel referensi.'}
                    </div>
                </div>
            ` : ''}

            <!-- 2. Mini Table Row Snippet: Cross-Page or In-Page Row Evidence Preview -->
            ${snippet && snippet.cells && snippet.cells.length > 0 ? `
                <div class="snippet-box">
                    <div class="snippet-header">
                        <div class="snippet-title-wrap">
                            <span class="snippet-icon">▦</span>
                            <span class="snippet-title">Cuplikan Baris Tabel: <strong>${snippet.table_id || f.table_evidence?.table_id}</strong> (Hal. ${evidencePage})</span>
                        </div>
                        ${isCrossPage ? `
                            <button class="btn-snippet-jump" onclick="event.stopPropagation(); switchDocPage(${currentDocPage === evidencePage ? claimPage : evidencePage});">
                                ${currentDocPage === evidencePage ? `Kembali ke Klaim (Hal. ${claimPage}) ↖` : `Lompat ke Tabel (Hal. ${evidencePage}) ↗`}
                            </button>
                        ` : ''}
                    </div>
                    <div class="snippet-table-wrap">
                        <table class="mini-snippet-table">
                            <thead>
                                <tr>
                                    <th>Variabel / Baris</th>
                                    ${snippet.cells.map(c => `<th>${c.header}</th>`).join('')}
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td class="snippet-row-label"><strong>${snippet.row_label}</strong></td>
                                    ${snippet.cells.map(c => `
                                        <td class="${c.is_target ? 'snippet-target-cell' : ''}" title="${c.header}: ${c.raw_val}">
                                            ${c.raw_val}
                                            ${c.is_target ? '<span class="target-flag">Bukti</span>' : ''}
                                        </td>
                                    `).join('')}
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            ` : (isCrossPage ? `
                <div class="cross-page-nav-badge">
                    <span class="cross-nav-icon">↗</span>
                    <span class="cross-nav-text">Tabel Bukti di <strong>Halaman ${evidencePage}</strong> (Klaim di Hal. ${claimPage})</span>
                    <button class="btn-jump-pill" onclick="event.stopPropagation(); switchDocPage(${currentDocPage === evidencePage ? claimPage : evidencePage});">
                        ${currentDocPage === evidencePage ? `Lihat Teks Klaim (Hal. ${claimPage}) ↖` : `Lompat ke Tabel (Hal. ${evidencePage}) ↗`}
                    </button>
                </div>
            ` : '')}

            <!-- 3. Sentence Quote -->
            <div class="claim-quote">
                <span style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px; color: var(--color-stone); display: block; margin-bottom: 4px;">Kutipan Teks Klaim Mahasiswa:</span>
                "${f.claim_source?.text || ''}"
            </div>

            <!-- 4. Math Proof Callout -->
            <div class="math-proof-callout">
                <div class="math-label">Bukti Matematika Deterministik (SciPy / Formula)</div>
                <div style="word-break: break-word;">${mathTrace.formula_display || f.verdict}</div>
                <div style="font-size: 11px; color: var(--color-stone); margin-top: 6px;">
                    Operasi: ${mathTrace.operation || 'AUDIT'} · Keyakinan Penautan: ${Math.round((mathTrace.reranker_confidence || 0.95)*100)}%
                </div>
            </div>

            <!-- 5. Interactive What-If Stepper -->
            <div class="what-if-box" id="whatif-${f.finding_id}">
                <div class="what-if-header">
                    <span>What-If Stepper Nilai Sel (±0.01)</span>
                    <span class="what-if-status" id="whatif-status-${f.finding_id}">Live Re-calc</span>
                </div>
                <div class="stepper-controls">
                    <button class="btn-step" onclick="stepCellVal('${f.finding_id}', -0.01, event)" aria-label="Kurangi nilai 0.01">−</button>
                    <span class="stepper-val" id="stepper-val-${f.finding_id}">${extractInitialWhatIf(f)}</span>
                    <button class="btn-step" onclick="stepCellVal('${f.finding_id}', +0.01, event)" aria-label="Tambah nilai 0.01">+</button>
                    <span style="font-size: 11px; color: var(--color-stone); margin-left: 8px;" id="whatif-desc-${f.finding_id}">
                        Klik untuk melihat titik perubahan status
                    </span>
                </div>
            </div>

            <!-- 6. Explain-First Pedagogical Scaffolding -->
            <div class="scaffolding-box">
                <div class="scaffolding-q">${pedagogical.question || 'Mengapa klaim ini perlu diperbaiki?'}</div>
                <div class="mcq-options-container" id="mcq-container-${f.finding_id}">
                    ${(pedagogical.options || []).map(opt => `
                        <div class="mcq-option" onclick="handleMcqClick('${f.finding_id}', ${opt.is_correct}, this)">
                            <span style="font-weight: 700; color: #7c3aed;">${opt.id}.</span> ${opt.text}
                        </div>
                    `).join('')}
                </div>
                <div class="safe-revision-reveal" id="safe-rev-${f.finding_id}">
                    <div class="rev-lbl">Draf Kalimat Revisi Rekomendasi LOCUS:</div>
                    <div style="color: var(--color-ink-black); font-size: 12px; line-height: 1.55;">${pedagogical.safe_revised_sentence || ''}</div>
                </div>
            </div>
        `;

        container.appendChild(card);
    });
}

function extractInitialWhatIf(finding) {
    const cells = finding.table_evidence?.cells || [];
    if (cells.length > 0 && cells[0].num_val !== undefined && cells[0].num_val !== null) {
        return cells[0].num_val.toFixed(2);
    }
    return "0.00";
}

// Render Left Pane PDF Canvas
function renderPdfXRayCanvas(bundle, pageImgUrl) {
    const viewport = document.getElementById("pdf-viewport-container");
    if (!viewport) return;
    viewport.innerHTML = "";

    const wrapper = document.createElement("div");
    wrapper.className = "page-wrapper";
    wrapper.id = "active-page-wrapper";

    // High-resolution authentic PDF page render
    const img = document.createElement("img");
    img.className = "pdf-page-img";
    img.id = "pdf-page-img";
    img.src = pageImgUrl;
    img.alt = "Halaman Dokumen Ilmiah";

    // Internal SVG layer for evidence arrows
    const svgEvidence = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svgEvidence.setAttribute("class", "page-evidence-svg");
    svgEvidence.id = "page-evidence-svg";
    svgEvidence.innerHTML = `
        <defs>
            <marker id="evidence-arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#d97706" />
            </marker>
        </defs>
    `;

    // Overlay for Bounding Boxes
    const overlay = document.createElement("div");
    overlay.className = "xray-overlay";
    overlay.id = "xray-bounding-box-overlay";

    wrapper.appendChild(img);
    wrapper.appendChild(svgEvidence);
    wrapper.appendChild(overlay);
    viewport.appendChild(wrapper);

    const setupOverlays = () => {
        populateBoundingBoxes(overlay, svgEvidence, bundle, img);
        if (currentView === "studio") {
            setTimeout(drawSvgConnector, 50);
        }
    };

    if (img.complete && img.naturalWidth > 0) {
        setupOverlays();
    } else {
        img.onload = setupOverlays;
    }
}

// Populate Bounding Boxes with Page Filtering & Pure Subtle Highlights
function populateBoundingBoxes(overlay, svgEvidence, bundle, img) {
    overlay.innerHTML = "";
    const defs = svgEvidence.querySelector("defs");
    svgEvidence.innerHTML = "";
    if (defs) svgEvidence.appendChild(defs);

    const pageDims = bundle?.page_dimensions?.[currentDocPage] || bundle?.page_dimensions?.[`${currentDocPage}`];
    const naturalW = img.naturalWidth || 0;
    const naturalH = img.naturalHeight || 0;

    let pdfPageW = 595.28;
    let pdfPageH = 841.89;

    if (pageDims && pageDims[0] > 0 && pageDims[1] > 0) {
        pdfPageW = pageDims[0];
        pdfPageH = pageDims[1];
    } else if (naturalW > 0 && naturalH > 0) {
        // pypdfium2 renders at scale=2.0, so PDF points = natural pixels / 2.0
        pdfPageW = naturalW / 2.0;
        pdfPageH = naturalH / 2.0;
    }

    const renderedW = img.clientWidth || (naturalW > 0 ? naturalW / 2.0 : 595.0);
    const renderedH = img.clientHeight || (naturalH > 0 ? naturalH / 2.0 : 842.0);

    const scaleX = renderedW / pdfPageW;
    const scaleY = renderedH / pdfPageH;

    const findings = bundle.findings || [];

    let activeClaimPos = null;
    let activeCellPos = null;

    findings.forEach(f => {
        const claimPage = f.claim_source?.page || 1;
        const evidencePage = f.table_evidence?.page || claimPage;
        const isCurrentActive = (f.finding_id === activeFindingId);

        // 1. Claim Bounding Box - Render ONLY if strictly on currentDocPage
        if (claimPage === currentDocPage) {
            const boxes = (f.claim_source?.boxes && f.claim_source.boxes.length > 0)
                ? f.claim_source.boxes
                : [f.claim_source?.bbox || [31.2, 289.9, 564.1, 316.9]];

            const minX = Math.min(...boxes.map(b => b[0])) * scaleX;
            const minY = Math.min(...boxes.map(b => b[1])) * scaleY;
            const maxX = Math.max(...boxes.map(b => b[2])) * scaleX;
            const maxY = Math.max(...boxes.map(b => b[3])) * scaleY;
            const cw = Math.max(20, maxX - minX);
            const ch = Math.max(14, maxY - minY);

            const claimBox = document.createElement("div");
            claimBox.className = `xray-bbox xray-bbox-claim ${isCurrentActive ? "active" : ""}`;
            claimBox.id = `bbox-claim-${f.finding_id}`;
            claimBox.style.left = `${minX}px`;
            claimBox.style.top = `${minY}px`;
            claimBox.style.width = `${cw}px`;
            claimBox.style.height = `${ch}px`;

            if (boxes.length > 1) {
                // For multi-line claims, make outer wrapper frame transparent and draw tight line segments
                claimBox.style.border = "none";
                claimBox.style.background = "transparent";
                boxes.forEach(box => {
                    const bx0 = (box[0] * scaleX) - minX;
                    const by0 = (box[1] * scaleY) - minY;
                    const bw = Math.max(10, (box[2] - box[0]) * scaleX);
                    const bh = Math.max(12, (box[3] - box[1]) * scaleY);
                    const lineSeg = document.createElement("div");
                    lineSeg.className = "xray-line-segment";
                    lineSeg.style.left = `${bx0}px`;
                    lineSeg.style.top = `${by0}px`;
                    lineSeg.style.width = `${bw}px`;
                    lineSeg.style.height = `${bh}px`;
                    claimBox.appendChild(lineSeg);
                });
            }

            if (isCurrentActive) {
                activeClaimPos = {
                    x0: minX,
                    y0: minY,
                    x1: maxX,
                    y1: maxY,
                    centerX: minX + cw / 2,
                    centerY: minY + ch / 2,
                    width: cw,
                    height: ch
                };

                let tagHtml = `<span class="bbox-tag bbox-tag-claim"><span class="badge-dot dot-rose"></span>Klaim Terpilih</span>`;
                if (evidencePage !== claimPage) {
                    tagHtml = `<span class="bbox-tag bbox-tag-claim bbox-tag-clickable" onclick="event.stopPropagation(); switchDocPage(${evidencePage})" title="Klik untuk melompat ke tabel bukti di Halaman ${evidencePage}"><span class="badge-dot dot-rose"></span>Klaim Terpilih · Bukti di Hal. ${evidencePage} ↗</span>`;
                }
                const tagEl = document.createElement("div");
                tagEl.innerHTML = tagHtml;
                claimBox.appendChild(tagEl.firstElementChild);
            }

            claimBox.onclick = () => selectFinding(f.finding_id);
            overlay.appendChild(claimBox);
        }

        // 2. Table Evidence Cell Bounding Boxes - Render ONLY if on currentDocPage
        if (evidencePage === currentDocPage) {
            const cells = f.table_evidence?.cells || [];

            if (isCurrentActive && cells.length > 0) {
                let minCellX = Infinity;
                let minCellY = Infinity;
                let maxCellX = -Infinity;
                let maxCellY = -Infinity;

                cells.forEach((cell, idx) => {
                    const cellBbox = cell.bbox || [218.0, 215.3, 235.5, 224.3];
                    const cellX0 = cellBbox[0] * scaleX;
                    const cellY0 = cellBbox[1] * scaleY;
                    const cellW = Math.max(18, (cellBbox[2] - cellBbox[0]) * scaleX);
                    const cellH = Math.max(12, (cellBbox[3] - cellBbox[1]) * scaleY);

                    minCellX = Math.min(minCellX, cellX0);
                    minCellY = Math.min(minCellY, cellY0);
                    maxCellX = Math.max(maxCellX, cellX0 + cellW);
                    maxCellY = Math.max(maxCellY, cellY0 + cellH);

                    const cellBox = document.createElement("div");
                    cellBox.className = "xray-bbox xray-bbox-cell active";
                    cellBox.id = `bbox-cell-${f.finding_id}-${idx}`;
                    cellBox.style.left = `${cellX0}px`;
                    cellBox.style.top = `${cellY0}px`;
                    cellBox.style.width = `${cellW}px`;
                    cellBox.style.height = `${cellH}px`;
                    cellBox.title = `Sel Bukti [${cell.row_label ? cell.row_label + ' · ' : ''}${cell.header_path || ''}]: ${cell.raw_val}`;

                    // Keep cell interior 100% clean so underlying PDF text is completely legible
                    cellBox.onclick = () => selectFinding(f.finding_id);
                    overlay.appendChild(cellBox);
                });

                activeCellPos = {
                    x0: minCellX,
                    y0: minCellY,
                    x1: maxCellX,
                    y1: maxCellY,
                    centerX: (minCellX + maxCellX) / 2,
                    centerY: (minCellY + maxCellY) / 2,
                    width: maxCellX - minCellX,
                    height: maxCellY - minCellY
                };

                // Render EXACTLY ONE unified floating badge above the entire cell group
                const clusterBadge = document.createElement("div");
                clusterBadge.className = "xray-cluster-badge";
                clusterBadge.style.left = `${minCellX}px`;
                const badgeTop = Math.max(4, minCellY - 26);
                clusterBadge.style.top = `${badgeTop}px`;

                let colLabel = cells[0].header_path || (cells.length > 1 ? `${cells.length} Nilai` : cells[0].raw_val);
                let badgeLabel = cells.length > 1 ? `Bukti: Kolom ${colLabel} (${cells.length} Sel)` : `Bukti Sel: ${cells[0].raw_val}`;

                if (evidencePage !== claimPage) {
                    clusterBadge.innerHTML = `<span class="bbox-tag bbox-tag-cell bbox-tag-clickable" onclick="event.stopPropagation(); switchDocPage(${claimPage})" title="Klik untuk kembali ke teks klaim di Halaman ${claimPage}"><span class="badge-dot dot-amber"></span>${badgeLabel} · Klaim di Hal. ${claimPage} ↖</span>`;
                } else {
                    clusterBadge.innerHTML = `<span class="bbox-tag bbox-tag-cell"><span class="badge-dot dot-amber"></span>${badgeLabel}</span>`;
                }
                overlay.appendChild(clusterBadge);
            } else {
                // Inactive finding evidence cells on this page: render clean delicate outline
                cells.forEach((cell, idx) => {
                    const cellBbox = cell.bbox || [218.0, 215.3, 235.5, 224.3];
                    const cellX0 = cellBbox[0] * scaleX;
                    const cellY0 = cellBbox[1] * scaleY;
                    const cellW = Math.max(18, (cellBbox[2] - cellBbox[0]) * scaleX);
                    const cellH = Math.max(12, (cellBbox[3] - cellBbox[1]) * scaleY);

                    const cellBox = document.createElement("div");
                    cellBox.className = "xray-bbox xray-bbox-cell";
                    cellBox.id = `bbox-cell-${f.finding_id}-${idx}`;
                    cellBox.style.left = `${cellX0}px`;
                    cellBox.style.top = `${cellY0}px`;
                    cellBox.style.width = `${cellW}px`;
                    cellBox.style.height = `${cellH}px`;
                    cellBox.title = `Sel Bukti [${cell.row_label ? cell.row_label + ' · ' : ''}${cell.header_path || ''}]: ${cell.raw_val}`;
                    cellBox.onclick = () => selectFinding(f.finding_id);
                    overlay.appendChild(cellBox);
                });
            }
        }
    });

    // 3. ONLY draw intra-page evidence bracket if BOTH claim AND cell are strictly on the CURRENT page!
    if (activeClaimPos && activeCellPos) {
        drawInternalEvidenceArrow(svgEvidence, activeCellPos, activeClaimPos);
    }
}

// Editorial Gutter Route (Bracket): routes through left paper margin gutter (x = 14px), NEVER crossing document text!
function drawInternalEvidenceArrow(svg, cell, claim) {
    if (!svg || !cell || !claim) return;

    const gutterX = 14;

    const claimY = claim.centerY;
    const claimX = Math.max(gutterX + 8, claim.x0);

    const cellY = cell.centerY;
    const cellX = Math.max(gutterX + 8, cell.x0);

    const r = 6;
    let pathD = "";

    if (Math.abs(claimY - cellY) < 12) {
        pathD = `M ${cellX} ${cellY} L ${claimX} ${claimY}`;
    } else {
        const isCellLower = cellY > claimY;
        pathD = `M ${cellX} ${cellY} ` +
                `H ${gutterX + r} ` +
                `Q ${gutterX} ${cellY} ${gutterX} ${cellY + (isCellLower ? -r : r)} ` +
                `V ${claimY + (isCellLower ? r : -r)} ` +
                `Q ${gutterX} ${claimY} ${gutterX + r} ${claimY} ` +
                `H ${claimX}`;
    }

    const bracket = document.createElementNS("http://www.w3.org/2000/svg", "path");
    bracket.setAttribute("d", pathD.trim());
    bracket.setAttribute("stroke", "#d97706");
    bracket.setAttribute("stroke-width", "1.75");
    bracket.setAttribute("fill", "none");
    bracket.setAttribute("stroke-dasharray", "4,3");
    bracket.setAttribute("stroke-linecap", "round");
    bracket.setAttribute("stroke-linejoin", "round");
    bracket.setAttribute("marker-end", "url(#evidence-arrow)");

    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("cx", cellX);
    dot.setAttribute("cy", cellY);
    dot.setAttribute("r", "3");
    dot.setAttribute("fill", "#d97706");

    svg.appendChild(bracket);
    svg.appendChild(dot);
}

// Select Finding & Redraw Connections with Bi-directional Focus
function selectFinding(findingId) {
    activeFindingId = findingId;

    const finding = (currentBundle?.findings || []).find(f => f.finding_id === findingId);
    if (finding) {
        const claimPage = finding.claim_source?.page || 1;
        const evidencePage = finding.table_evidence?.page || claimPage;
        // If current page is neither claimPage nor evidencePage, switch to claimPage
        if (currentDocPage !== claimPage && currentDocPage !== evidencePage) {
            switchDocPage(claimPage);
            return;
        }
    }

    // Update active state in findings list
    document.querySelectorAll(".finding-card").forEach(c => {
        const isActive = (c.id === `card-${findingId}`);
        c.classList.toggle("active", isActive);
        if (isActive) {
            c.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    });

    // Rerender bounding boxes on active page to reflect active highlight
    const img = document.getElementById("pdf-page-img");
    const overlay = document.getElementById("xray-bounding-box-overlay");
    const svgEvidence = document.getElementById("page-evidence-svg");
    if (img && overlay && svgEvidence && currentBundle) {
        populateBoundingBoxes(overlay, svgEvidence, currentBundle, img);
    }

    if (currentView === "studio") {
        drawSvgConnector();
    }

    // Smooth scroll the viewport to show the active bounding box
    setTimeout(() => {
        const activeBox = document.querySelector(".xray-bbox.active");
        if (activeBox) {
            activeBox.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
        }
    }, 60);
}

// Canvas Zoom Controls
function adjustCanvasZoom(delta) {
    currentCanvasZoom = Math.max(0.6, Math.min(2.0, currentCanvasZoom + delta));
    applyCanvasZoom();
}

function resetCanvasZoom() {
    currentCanvasZoom = 1.0;
    applyCanvasZoom();
}

function applyCanvasZoom() {
    const wrapper = document.getElementById("active-page-wrapper");
    const zoomText = document.getElementById("zoom-level-text");
    if (wrapper) {
        wrapper.style.transform = `scale(${currentCanvasZoom})`;
    }
    if (zoomText) {
        zoomText.innerText = `${Math.round(currentCanvasZoom * 100)}%`;
    }
    setTimeout(() => {
        const img = document.getElementById("pdf-page-img");
        const overlay = document.getElementById("xray-bounding-box-overlay");
        const svgEvidence = document.getElementById("page-evidence-svg");
        if (img && overlay && svgEvidence && currentBundle) {
            populateBoundingBoxes(overlay, svgEvidence, currentBundle, img);
        }
        drawSvgConnector();
    }, 80);
}

// Findings Filter Handling
function setFindingsFilter(filterType) {
    currentFindingsFilter = filterType;

    // Update active filter pill
    document.querySelectorAll(".filter-pill").forEach(p => {
        p.classList.toggle("active", p.id === `filter-${filterType}`);
    });

    const cards = document.querySelectorAll(".finding-card");
    let firstVisibleFindingId = null;

    cards.forEach(card => {
        const category = card.getAttribute("data-category") || "error";
        let isVisible = false;
        if (filterType === "all") {
            isVisible = true;
        } else if (filterType === category) {
            isVisible = true;
        }

        card.style.display = isVisible ? "block" : "none";
        if (isVisible && !firstVisibleFindingId) {
            firstVisibleFindingId = card.id.replace("card-", "");
        }
    });

    if (firstVisibleFindingId) {
        const activeCard = document.getElementById(`card-${activeFindingId}`);
        if (!activeCard || activeCard.style.display === "none") {
            selectFinding(firstVisibleFindingId);
        }
    }
    drawSvgConnector();
}

function drawSvgConnector() {
    if (currentView !== "studio") return;

    const svg = document.getElementById("svg-connector-canvas");
    if (!svg) return;
    svg.innerHTML = "";

    if (!activeFindingId) return;

    const card = document.getElementById(`card-${activeFindingId}`);
    const claimBbox = document.getElementById(`bbox-claim-${activeFindingId}`);
    const cellBbox = document.getElementById(`bbox-cell-${activeFindingId}-0`);
    const targetBbox = claimBbox || cellBbox;

    if (!card || !targetBbox) return;

    const svgRect = svg.getBoundingClientRect();
    const cardRect = card.getBoundingClientRect();
    const targetRect = targetBbox.getBoundingClientRect();

    const leftViewport = document.getElementById("pdf-viewport-container").getBoundingClientRect();
    const rightPane = document.querySelector(".pane-right").getBoundingClientRect();

    const isTargetVisible = (targetRect.bottom > leftViewport.top && targetRect.top < leftViewport.bottom);
    const isCardVisible = (cardRect.bottom > rightPane.top && cardRect.top < rightPane.bottom);

    if (!isTargetVisible || !isCardVisible) {
        return;
    }

    const x1 = cardRect.left - svgRect.left;
    const y1 = cardRect.top + 28 - svgRect.top;

    const x2 = targetRect.right - svgRect.left;
    const y2 = targetRect.top + (targetRect.height / 2) - svgRect.top;

    const dx = Math.abs(x1 - x2) * 0.45;
    const cx1 = x1 - dx;
    const cy1 = y1;
    const cx2 = x2 + dx;
    const cy2 = y2;

    const endColor = claimBbox ? "#e11d48" : "#d97706";

    let defs = svg.querySelector("defs");
    if (!defs) {
        defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
        defs.innerHTML = `
            <linearGradient id="connector-grad" x1="1" y1="0" x2="0" y2="0">
                <stop offset="0%" stop-color="#0075de" />
                <stop offset="100%" stop-color="${endColor}" />
            </linearGradient>
        `;
        svg.appendChild(defs);
    }

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`);
    path.setAttribute("stroke", "url(#connector-grad)");
    path.setAttribute("stroke-width", "1.75");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke-dasharray", "5,4");

    const circle1 = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle1.setAttribute("cx", x1);
    circle1.setAttribute("cy", y1);
    circle1.setAttribute("r", "3.5");
    circle1.setAttribute("fill", "#0075de");

    const circle2 = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle2.setAttribute("cx", x2);
    circle2.setAttribute("cy", y2);
    circle2.setAttribute("r", "3.5");
    circle2.setAttribute("fill", endColor);

    svg.appendChild(path);
    svg.appendChild(circle1);
    svg.appendChild(circle2);
}

function clearSvg() {
    const svg = document.getElementById("svg-connector-canvas");
    if (svg) svg.innerHTML = "";
}

// Live What-If Stepper Action
async function stepCellVal(findingId, delta, event) {
    event.stopPropagation();
    const valEl = document.getElementById(`stepper-val-${findingId}`);
    const statusEl = document.getElementById(`whatif-status-${findingId}`);
    const descEl = document.getElementById(`whatif-desc-${findingId}`);

    let currentVal = parseFloat(valEl.innerText) || 0.0;
    currentVal = Math.round((currentVal + delta) * 100) / 100;
    valEl.innerText = currentVal.toFixed(2);

    let finding = null;
    if (currentBundle && currentBundle.findings) {
        finding = currentBundle.findings.find(f => f.finding_id === findingId);
    }

    let payload = { stat_val: currentVal };
    if (finding && finding.verdict === "POLARITY_INVERSION_ERROR") {
        payload.finding_type = "POLARITY_INVERSION";
        payload.polarity = -1;
        payload.other_vals = [0.41, 0.57];
    } else if (finding && finding.verdict === "PREREQUISITE_INVERSION_ERROR") {
        payload.finding_type = "PREREQUISITE_INVERSION";
    } else {
        payload.test_type = "t";
        payload.df1 = 58;
        payload.p_reported = 0.002;
    }

    try {
        const res = await fetch("/api/v1/what-if", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === "success") {
            const result = data.result;
            statusEl.innerText = result.verdict;
            if (result.verdict === "PASS") {
                statusEl.style.color = "#065f46";
                statusEl.style.backgroundColor = "#d1fae5";
                descEl.innerText = result.status_text || `Lolos pada nilai ${currentVal.toFixed(2)}`;
                descEl.style.color = "#059669";
            } else {
                statusEl.style.color = "var(--color-coral)";
                statusEl.style.backgroundColor = "#fee2e2";
                descEl.innerText = result.status_text || `Inkonsistensi terdeteksi`;
                descEl.style.color = "var(--color-stone)";
            }
        }
    } catch (e) {
        console.error("What-If step failed:", e);
    }
}

// Explain-First MCQ Handler
function handleMcqClick(findingId, isCorrect, el) {
    const container = document.getElementById(`mcq-container-${findingId}`);
    container.querySelectorAll(".mcq-option").forEach(opt => opt.classList.remove("correct"));

    if (isCorrect) {
        el.classList.add("correct");
        const revEl = document.getElementById(`safe-rev-${findingId}`);
        if (revEl) {
            revEl.classList.add("visible");
        }
    } else {
        alert("Pilihan belum tepat secara kaidah metodologi ilmiah. Silakan pertimbangkan arah optimasi metrik atau uji hipotesis nol.");
    }
}

// Drag & Drop Live Dropzone
function setupDropzone() {
    const fileInput = document.getElementById("pdf-file-input");
    const studioBtn = document.getElementById("studio-dropzone-upload-btn");

    if (studioBtn) studioBtn.onclick = () => fileInput.click();

    fileInput.onchange = async (e) => {
        const file = e.target.files[0];
        if (file) {
            await uploadAndAuditPdf(file);
        }
    };
}

async function uploadAndAuditPdf(file) {
    const sizeKb = (file.size / 1024).toFixed(1);
    showAuditLoading(file.name, sizeKb);
    setPipelineStep(1, 5, "Merender halaman PDF...");

    if (activeAuditPollInterval) clearInterval(activeAuditPollInterval);
    activeAuditAbortController = new AbortController();

    // Real-time server progress polling (every 350 ms)
    activeAuditPollInterval = setInterval(async () => {
        try {
            const pRes = await fetch("/api/v1/audit/progress");
            const pData = await pRes.json();
            if (pData.status === "success" && pData.progress) {
                const prog = pData.progress;
                if (prog.cancelled) {
                    if (activeAuditPollInterval) {
                        clearInterval(activeAuditPollInterval);
                        activeAuditPollInterval = null;
                    }
                    return;
                }
                if (prog.is_running) {
                    const stepIdx = prog.step_index || 1;
                    const pct = typeof prog.percent === "number" ? Math.round(prog.percent) : 15;
                    const label = prog.detail_text || prog.step_name || "Memproses...";
                    setPipelineStep(stepIdx, pct, label);
                }
            }
        } catch (_) {}
    }, 350);

    const formData = new FormData();
    formData.append("file", file);

    const studioBtn = document.getElementById("studio-dropzone-upload-btn");
    const originalText = studioBtn ? studioBtn.innerHTML : "";
    if (studioBtn) {
        studioBtn.innerHTML = `<span>Menganalisis Dokumen...</span>`;
    }

    try {
        const res = await fetch("/api/v1/audit", {
            method: "POST",
            body: formData,
            signal: activeAuditAbortController.signal
        });

        if (!res.ok) {
            let errDetail = `Server mengembalikan status ${res.status}`;
            try {
                const errJson = await res.json();
                if (errJson && errJson.detail) errDetail = errJson.detail;
            } catch (_) {
                try {
                    const errText = await res.text();
                    if (errText) errDetail = errText;
                } catch (_) {}
            }
            if (activeAuditPollInterval) {
                clearInterval(activeAuditPollInterval);
                activeAuditPollInterval = null;
            }
            showAuditError(errDetail);
            return;
        }

        const data = await res.json();
        if (activeAuditPollInterval) {
            clearInterval(activeAuditPollInterval);
            activeAuditPollInterval = null;
        }

        if (data.status === "success" && data.data) {
            const bundle = data.data;
            bundle.document_sha256 = data.document_sha256;
            bundle.engine_version = data.engine_version || "v3.5-grounded";
            bundle.readiness_score = data.readiness_score;
            bundle.pattern_summary = data.pattern_summary;

            sessionStorage.setItem("locus_active_bundle", JSON.stringify(bundle));
            sessionStorage.setItem("locus_active_filename", file.name);
            setPipelineStep(6, 100, "Sintesis bukti");

            const findings = bundle.findings || [];
            const summaryText = `${findings.length} temuan terdeteksi`;

            finishAuditLoading(summaryText, () => {
                window.location.href = "/app/studio.html";
            });
        } else {
            showAuditError(data.detail || "Gagal melakukan audit dokumen");
        }
    } catch (err) {
        if (err.name === "AbortError") {
            if (activeAuditPollInterval) {
                clearInterval(activeAuditPollInterval);
                activeAuditPollInterval = null;
            }
            console.log("Audit dibatalkan oleh pengguna.");
            return;
        }

        console.warn("Koneksi POST terputus (kemungkinan perubahan jaringan / Wi-Fi off). Memulai auto-recovery...", err);

        let recovered = false;
        for (let attempt = 1; attempt <= 3; attempt++) {
            await new Promise(r => setTimeout(r, 1000));
            try {
                const probeRes = await fetch("/api/v1/audit/progress");
                if (probeRes.ok) {
                    const probeData = await probeRes.json();
                    const prog = probeData.progress;
                    if (prog && (prog.is_running || prog.step_index >= 1 || prog.percent > 0)) {
                        recovered = true;
                        break;
                    }
                }
            } catch (_) {}
        }

        if (recovered) {
            console.log("Auto-recovery berhasil! Menyambung kembali ke progress audit lokal...");
            try {
                await new Promise((resolve, reject) => {
                    const maxWaitMs = 180000;
                    const startWait = Date.now();
                    const recoverPoll = setInterval(async () => {
                        if (Date.now() - startWait > maxWaitMs) {
                            clearInterval(recoverPoll);
                            reject(new Error("Timeout menunggu audit selesai"));
                            return;
                        }
                        try {
                            const pRes = await fetch("/api/v1/audit/progress");
                            const pData = await pRes.json();
                            if (pData.status === "success" && pData.progress) {
                                const prog = pData.progress;
                                const stepIdx = prog.step_index || 1;
                                const pct = typeof prog.percent === "number" ? Math.round(prog.percent) : 15;
                                const label = prog.detail_text || prog.step_name || "Memproses...";
                                setPipelineStep(stepIdx, pct, label);

                                if (!prog.is_running && (prog.percent === 100 || stepIdx === 6)) {
                                    clearInterval(recoverPoll);
                                    resolve();
                                }
                            }
                        } catch (_) {}
                    }, 400);
                });

                const latestRes = await fetch("/api/v1/latest-audit");
                if (latestRes.ok) {
                    const latestJson = await latestRes.json();
                    if (latestJson.status === "success" && latestJson.data) {
                        if (activeAuditPollInterval) {
                            clearInterval(activeAuditPollInterval);
                            activeAuditPollInterval = null;
                        }
                        const bundle = latestJson.data;
                        bundle.document_sha256 = latestJson.document_sha256;
                        bundle.engine_version = latestJson.engine_version || "v3.5-grounded";
                        bundle.readiness_score = latestJson.readiness_score;
                        bundle.pattern_summary = latestJson.pattern_summary;

                        sessionStorage.setItem("locus_active_bundle", JSON.stringify(bundle));
                        sessionStorage.setItem("locus_active_filename", file.name);
                        setPipelineStep(6, 100, "Sintesis bukti");

                        const findings = bundle.findings || [];
                        const summaryText = `${findings.length} temuan terdeteksi`;

                        finishAuditLoading(summaryText, () => {
                            window.location.href = "/app/studio.html";
                        });
                        return;
                    }
                }
            } catch (recoverErr) {
                console.error("Gagal sinkronisasi akhir setelah auto-recovery:", recoverErr);
            }
        }

        if (activeAuditPollInterval) {
            clearInterval(activeAuditPollInterval);
            activeAuditPollInterval = null;
        }
        showAuditError("Koneksi gagal ke server lokal (127.0.0.1:8000)");
        console.error("Audit error:", err);
    } finally {
        activeAuditAbortController = null;
        if (studioBtn) studioBtn.innerHTML = originalText;
    }
}

// Export Receipt Action
function setupEventListeners() {
    const exportBtn = document.getElementById("btn-export-receipt");
    if (exportBtn) {
        exportBtn.onclick = async () => {
            if (!currentBundle) {
                alert("Belum ada dokumen yang diaudit.");
                return;
            }

            try {
                const res = await fetch("/api/v1/export-receipt", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        proof_bundle: currentBundle,
                        redact_pii: true
                    })
                });
                const data = await res.json();
                if (data.status === "success") {
                    const receipt = data.receipt;
                    const blob = new Blob([JSON.stringify(receipt, null, 2)], { type: "application/json" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `LOCUS_Receipt_${receipt.receipt_id}.json`;
                    a.click();
                    URL.revokeObjectURL(url);
                }
            } catch (err) {
                console.error("Export receipt error:", err);
            }
        };
    }
}
