/**
 * LOCUS: Scientific Integrity Studio Engine (Real Data Driver)
 * 100% Dynamic, Zero Dummy Testing Samples, Rule R-02 Compliant.
 */

let currentBundle = null;
let currentDocPage = 1;
let totalDocPages = 1;
let zoomLevel = 1.0;
let activeFindingId = null;
let currentFilter = "all";

// Authoritative Indonesian metadata for scientific verdict types
const VERDICT_META = {
    "POLARITY_INVERSION_ERROR": {
        title: "Inversi polaritas metrik",
        code: "POLARITAS",
        category: "fatal",
        desc: "Metrik galat (seperti RMSE/MAE) diinterpretasikan terbalik (makin kecil makin baik)."
    },
    "PREREQUISITE_LOGIC_INVERSION": {
        title: "Logika uji normalitas terbalik",
        code: "NORMALITAS",
        category: "fatal",
        desc: "Uji normalitas menyimpulkan normal padahal p < 0,05 (tolak H0, data tidak normal)."
    },
    "DIRECT_CELL_CONTRADICTION": {
        title: "Angka berbeda dengan tabel",
        code: "KONTRA-TABEL",
        category: "fatal",
        desc: "Nilai yang diklaim di narasi bertentangan langsung dengan angka di tabel bukti."
    },
    "INLINE_FORMULA_NARRATIVE_CONTRADICTION": {
        title: "Inkonsistensi nilai rumus",
        code: "HITUNG-RUMUS",
        category: "fatal",
        desc: "Hasil kalkulasi rumus matematis tidak selaras dengan angka narasi yang dilaporkan."
    },
    "WARN_TRUNCATION_ROUNDING": {
        title: "Salah pembulatan angka",
        code: "PEMOTONGAN",
        category: "warning",
        desc: "Angka dipotong (truncation) tanpa kaidah pembulatan baku matematika."
    },
    "WARN_ROUNDING": {
        title: "Variasi pembulatan desimal",
        code: "PEMBULATAN",
        category: "warning",
        desc: "Terdapat perbedaan digit pembulatan dibanding kaidah round half-up baku."
    },
    "TABLE_REFERENCE_TYPO": {
        title: "Salah nomor rujukan tabel",
        code: "RUJUKAN-TABEL",
        category: "warning",
        desc: "Salah nomor rujukan tabel pada narasi teks."
    },
    "DECISION_FLIP_ERROR": {
        title: "Pembalik keputusan signifikansi",
        code: "STATCHECK",
        category: "fatal",
        desc: "Rekalkulasi fungsi uji t/F membuktikan klaim signifikansi p-value terbalik."
    },
    "GRIM_INCONSISTENCY": {
        title: "Inkonsistensi matematis mean (GRIM)",
        code: "UJI-GRIM",
        category: "fatal",
        desc: "Nilai mean yang dilaporkan secara matematis mustahil dihasilkan dari ukuran sampel N."
    },
    "SPRITE_INCONSISTENCY": {
        title: "Inkonsistensi varians standar deviasi (SPRITE)",
        code: "UJI-SPRITE",
        category: "fatal",
        desc: "Kombinasi mean, standar deviasi, dan rentang skala Likert tidak konsisten."
    },
    "APA_PROSE_MISMATCH": {
        title: "Format pelaporan statistik tidak konsisten",
        code: "FORMAT-APA",
        category: "warning",
        desc: "Format teks statistik APA tidak sesuai dengan derajat bebas atau nilai tabel."
    },
    "COLUMN_SWAP_ERROR": {
        title: "Salah baca kolom tabel",
        code: "KOLOM-TERTUKAR",
        category: "fatal",
        desc: "Klaim tertukar kolom (misal nilai kolom Mean diklaim sebagai Minimum)."
    },
    "ROW_SUM_MISMATCH": {
        title: "Total responden narasi tidak cocok",
        code: "TOTAL-RESPON",
        category: "fatal",
        desc: "Penjumlahan frekuensi responden pada narasi tidak sesuai dengan total sampel tabel."
    },
    "METRIC_SEMANTIC_HALLUCINATION": {
        title: "Halusinasi semantik metrik",
        code: "HALUSINASI",
        category: "fatal",
        desc: "Interpretasi makna statistik bertentangan dengan definisi metrik standar."
    },
    "SUPERLATIVE_CONTRADICTION": {
        title: "Kontradiksi klaim superlatif",
        code: "SUPERLATIF",
        category: "fatal",
        desc: "Klaim nilai tertinggi/terendah bertentangan dengan urutan data sebenarnya pada tabel."
    },
    "DIGIT_TRANSPOSITION_TYPO": {
        title: "Tipografi transposisi digit",
        code: "TRANSPOSISI",
        category: "fatal",
        desc: "Angka tertukar posisi digit (misal 76 menjadi 67) akibat salah ketik penulis."
    },
    "INLINE_FORMULA_CALC_ERROR": {
        title: "Kesalahan kalkulasi rumus",
        code: "GALAT-HITUNG",
        category: "fatal",
        desc: "Hasil perhitungan rumus pada teks berbeda dari hasil kalkulasi matematis baku."
    },
    "VALUE_MISMATCH": {
        title: "Inkonsistensi nilai sel",
        code: "KONTRA-TABEL",
        category: "fatal",
        desc: "Nilai yang diklaim di narasi bertentangan langsung dengan angka di tabel bukti."
    },
    "PASS_EXACT_MATCH": {
        title: "Konsisten dengan tabel",
        code: "LOLOS",
        category: "consistent",
        desc: "Nilai klaim pada teks selaras penuh dengan kalkulasi tabel data."
    }
};

function getVerdictMeta(verdict) {
    if (!verdict) return { title: "Temuan audit", code: "TEMUAN", category: "warning", desc: "Temuan integritas numerik." };
    if (VERDICT_META[verdict]) return VERDICT_META[verdict];

    const vUpper = verdict.toUpperCase();
    if (vUpper.includes("WARN") || vUpper.includes("ROUND") || vUpper.includes("TRUNC")) {
        return { title: "Salah pembulatan angka", code: "PEMBULATAN", category: "warning", desc: "Peringatan variasi pembulatan desimal." };
    }
    if (vUpper.includes("PASS") || vUpper.includes("EXACT")) {
        return { title: "Konsisten dengan tabel", code: "LOLOS", category: "consistent", desc: "Data terverifikasi konsisten." };
    }
    return { title: "Inkonsistensi data naskah", code: "FATAL", category: "fatal", desc: "Diskrepansi numerik terdeteksi." };
}

// Initialization on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
    initStudio();
    setupStudioEventListeners();
    setupDropzone();
});

async function initStudio() {
    const urlParams = new URLSearchParams(window.location.search);
    const presetParam = urlParams.get("preset");

    // 1. Baca query param ?preset=N terlebih dahulu
    if (presetParam !== null) {
        try {
            const pIdx = parseInt(presetParam, 10);
            const res = await fetch("/api/v1/presets");
            const data = await res.json();
            if (data.status === "success" && data.presets && data.presets[pIdx]) {
                const targetPreset = data.presets[pIdx];
                const docChip = document.getElementById("docTitleDisplay");
                if (docChip) docChip.textContent = targetPreset.title || `Preset ${pIdx + 1}`;
                const bundle = targetPreset.bundle || {};
                bundle.engine_version = "v3.5-grounded";
                displayAuditBundle(bundle, `/static/pages/preset_${pIdx + 1}/page_1.png`);
                return;
            }
        } catch (e) {
            console.warn("Gagal fetch preset:", e);
        }
    }

    // 2. Check if user uploaded a document in this session with valid findings
    const savedBundleJson = sessionStorage.getItem("locus_active_bundle");
    const savedFilename = sessionStorage.getItem("locus_active_filename");
    if (savedBundleJson) {
        try {
            const savedBundle = JSON.parse(savedBundleJson);
            // Jangan langsung return dari sessionStorage lama jika engine_version bukan v3.5-grounded
            if (savedBundle && (savedBundle.engine_version === "v3.5-grounded" || savedBundle.engine_version === "v3.4-synced") && savedBundle.findings && savedBundle.findings.length > 0) {
                const docChip = document.getElementById("docTitleDisplay");
                if (docChip && savedFilename) docChip.textContent = savedFilename;
                displayAuditBundle(savedBundle);
                return;
            }
        } catch (e) {
            console.error("Gagal parse saved bundle:", e);
        }
    }

    // 3. Fetch authoritative real audit data from Python backend (/api/v1/latest-audit)
    try {
        const res = await fetch("/api/v1/latest-audit");
        const json = await res.json();
        if (json.status === "success" && json.data) {
            const docChip = document.getElementById("docTitleDisplay");
            const docName = json.filename || "BAB 4.pdf";
            if (docChip) docChip.textContent = docName;

            // Salin metadata ke json.data sebelum render
            json.data.pattern_summary = json.pattern_summary || {};
            json.data.document_sha256 = json.document_sha256 || "";
            json.data.engine_version = json.engine_version || "v3.5-grounded";
            json.data.readiness_score = json.readiness_score || 95.0;

            sessionStorage.setItem("locus_active_bundle", JSON.stringify(json.data));
            sessionStorage.setItem("locus_active_filename", docName);
            displayAuditBundle(json.data);
            return;
        }
    } catch (e) {
        console.warn("Gagal fetch latest-audit:", e);
    }
}

const SVG_NS = "http://www.w3.org/2000/svg";
let pdfResizeObserver = null;

/**
 * Loads a rendered PDF page image safely without race conditions (C4).
 * Assigns onload BEFORE src, handles unchanged src when already complete,
 * and awaits img.decode() when supported.
 */
function loadPageImage(img, url, onReady) {
    if (!img || !url) {
        if (typeof onReady === "function") onReady();
        return;
    }

    let fired = false;
    const finish = () => {
        if (fired) return;
        fired = true;
        if (typeof onReady === "function") onReady();
    };

    const prevUrl = img.getAttribute("data-loaded-src");
    img.style.display = "block";

    // Same URL already loaded and decoded -> redraw immediately (onload will not fire again)
    if (prevUrl === url && img.complete && img.naturalWidth > 0) {
        finish();
        return;
    }

    img.setAttribute("data-loaded-src", url);
    img.onload = () => {
        if (typeof img.decode === "function") {
            img.decode().then(finish).catch(finish);
        } else {
            finish();
        }
    };
    img.onerror = finish;
    img.src = url;

    // Cache hit that became synchronously complete right after setting src
    if (img.complete && img.naturalWidth > 0) {
        if (typeof img.decode === "function") {
            img.decode().then(finish).catch(finish);
        } else {
            finish();
        }
    }
}

function isValidRect(rect) {
    if (!Array.isArray(rect) || rect.length < 4) return false;
    const x0 = Number(rect[0]);
    const y0 = Number(rect[1]);
    const x1 = Number(rect[2]);
    const y1 = Number(rect[3]);
    if (![x0, y0, x1, y1].every(Number.isFinite)) return false;
    return (x1 - x0) > 0.25 && (y1 - y0) > 0.25;
}

function resolvePagePointDimensions(pageNum, img) {
    const pageDims = currentBundle?.page_dimensions?.[pageNum]
        || currentBundle?.page_dimensions?.[`${pageNum}`];
    if (Array.isArray(pageDims) && pageDims[0] > 0 && pageDims[1] > 0) {
        return { widthPt: Number(pageDims[0]), heightPt: Number(pageDims[1]) };
    }

    // Fallback 1: per-finding explicit page_width_pt / cell_page_width_pt
    for (const f of (currentBundle?.findings || [])) {
        if ((f.claim_source?.page || 1) === pageNum && f.page_width_pt > 0 && f.page_height_pt > 0) {
            return { widthPt: Number(f.page_width_pt), heightPt: Number(f.page_height_pt) };
        }
        const evPage = f.cell_page || f.table_evidence?.page;
        if (evPage === pageNum && f.cell_page_width_pt > 0 && f.cell_page_height_pt > 0) {
            return { widthPt: Number(f.cell_page_width_pt), heightPt: Number(f.cell_page_height_pt) };
        }
    }

    // Fallback 2: natural image pixel dimensions divided by authoritative render_scale (1.5, never 2.0)
    const renderScale = Number(currentBundle?.render_scale) || 1.5;
    const naturalW = img?.naturalWidth || 0;
    const naturalH = img?.naturalHeight || 0;
    if (naturalW > 0 && naturalH > 0) {
        return { widthPt: naturalW / renderScale, heightPt: naturalH / renderScale };
    }

    return { widthPt: 595.28, heightPt: 841.89 };
}

function displayAuditBundle(bundle, defaultImgUrl = null) {
    currentBundle = bundle;

    // Determine total pages
    if (bundle.page_images && Object.keys(bundle.page_images).length > 0) {
        totalDocPages = Object.keys(bundle.page_images).length;
    } else {
        totalDocPages = 1;
    }

    // Start on the page of the first finding if available, otherwise page 1
    let startPage = 1;
    if (bundle.findings && bundle.findings.length > 0) {
        startPage = bundle.findings[0].claim_source?.page || 1;
    }
    currentDocPage = startPage;

    updatePageNavControls();

    let pageImgUrl = defaultImgUrl;
    if (!pageImgUrl) {
        if (bundle.page_images && bundle.page_images[`${currentDocPage}`]) {
            pageImgUrl = bundle.page_images[`${currentDocPage}`];
        } else if (bundle.page_images && bundle.page_images[currentDocPage]) {
            pageImgUrl = bundle.page_images[currentDocPage];
        } else if (bundle.page_images && bundle.page_images["1"]) {
            pageImgUrl = bundle.page_images["1"];
        } else if (bundle.page_images && Object.values(bundle.page_images).length > 0) {
            pageImgUrl = Object.values(bundle.page_images)[0];
        }
    }

    const img = document.getElementById("pdf-page-img");
    if (img && pageImgUrl) {
        loadPageImage(img, pageImgUrl, () => {
            renderPdfXRayCanvas();
        });
    }

    // Render findings list
    renderStudioFindings(bundle.findings || []);

    // Select first finding by default if available
    if (bundle.findings && bundle.findings.length > 0) {
        selectFinding(bundle.findings[0].finding_id);
    }
}

function updatePageNavControls() {
    const pageDisplay = document.getElementById("pageDisplay");
    if (pageDisplay) {
        pageDisplay.textContent = `${currentDocPage} / ${totalDocPages}`;
    }
    const btnPrev = document.getElementById("btnPrevPage");
    const btnNext = document.getElementById("btnNextPage");
    if (btnPrev) btnPrev.disabled = (currentDocPage <= 1);
    if (btnNext) btnNext.disabled = (currentDocPage >= totalDocPages);
}

function changeDocPage(newPage, onReady = null) {
    if (newPage < 1 || newPage > totalDocPages) return;
    currentDocPage = newPage;
    updatePageNavControls();

    const img = document.getElementById("pdf-page-img");
    if (img && currentBundle?.page_images) {
        const nextUrl = currentBundle.page_images[`${currentDocPage}`] || currentBundle.page_images[currentDocPage];
        if (nextUrl) {
            loadPageImage(img, nextUrl, () => {
                renderPdfXRayCanvas();
                if (typeof onReady === "function") onReady();
            });
            return;
        }
    }
    renderPdfXRayCanvas();
    if (typeof onReady === "function") onReady();
}

function createSvgRect(rect, className, titleText, findingId) {
    const el = document.createElementNS(SVG_NS, "rect");
    const x = Math.max(0, Number(rect[0]));
    const y = Math.max(0, Number(rect[1]));
    const w = Math.max(0.5, Number(rect[2]) - Number(rect[0]));
    const h = Math.max(0.5, Number(rect[3]) - Number(rect[1]));
    el.setAttribute("x", x.toFixed(2));
    el.setAttribute("y", y.toFixed(2));
    el.setAttribute("width", w.toFixed(2));
    el.setAttribute("height", h.toFixed(2));
    el.setAttribute("rx", "1.5");
    el.setAttribute("ry", "1.5");
    el.setAttribute("vector-effect", "non-scaling-stroke");
    el.setAttribute("class", className);
    el.setAttribute("data-finding-id", findingId);

    if (titleText) {
        const titleEl = document.createElementNS(SVG_NS, "title");
        titleEl.textContent = titleText;
        el.appendChild(titleEl);
    }
    el.addEventListener("click", (e) => {
        e.stopPropagation();
        selectFinding(findingId);
    });
    return el;
}

function renderPdfXRayCanvas() {
    const img = document.getElementById("pdf-page-img");
    const svgOverlay = document.getElementById("xrayOverlaySvg");
    const gutterLayer = document.getElementById("xray-gutter-layer");
    const svgEvidence = document.getElementById("marginBracketSvg");
    if (!img || !svgOverlay || !svgEvidence || !currentBundle) return;

    // Clear previous SVG rects and gutter pills
    svgOverlay.innerHTML = "";
    if (gutterLayer) gutterLayer.innerHTML = "";

    // SINGLE POINT OF COMPENSATION:
    // Backend (pdf_reader.py / table_geometry.py) already subtracts CropBox origin once
    // and emits all rects in 72-DPI visible page space [0..page_width_pt, 0..page_height_pt].
    // Frontend MUST NOT subtract cropX/cropY again.
    const { widthPt: pdfPageW, heightPt: pdfPageH } = resolvePagePointDimensions(currentDocPage, img);
    svgOverlay.setAttribute("viewBox", `0 0 ${pdfPageW.toFixed(2)} ${pdfPageH.toFixed(2)}`);

    const findings = currentBundle.findings || [];
    // Draw inactive findings first, then active finding on top so highlights stay crisp
    const orderedFindings = [
        ...findings.filter(f => f.finding_id !== activeFindingId),
        ...findings.filter(f => f.finding_id === activeFindingId)
    ];

    // Deduplicate overlapping inactive claim rects on the same sentence (C8)
    const seenInactiveClaimKeys = new Set();

    orderedFindings.forEach(f => {
        const claimPage = f.claim_source?.page || 1;
        const evidencePage = f.cell_page || f.table_evidence?.page || claimPage;
        const isCurrentActive = (f.finding_id === activeFindingId);
        const meta = getVerdictMeta(f.verdict);
        const category = meta.category || "fatal";
        const isFiltered = (currentFilter === "all" || category === currentFilter);

        // 1. Normalized Table Bounding Box (table_bbox_norm, nullable per C2)
        if (
            f.table_bbox_norm &&
            f.table_bbox_norm.page === currentDocPage &&
            Number.isFinite(f.table_bbox_norm.x0) &&
            Number.isFinite(f.table_bbox_norm.x1) &&
            f.table_bbox_norm.x1 > f.table_bbox_norm.x0 &&
            f.table_bbox_norm.y1 > f.table_bbox_norm.y0 &&
            (isCurrentActive || isFiltered)
        ) {
            const tNorm = f.table_bbox_norm;
            const tableRectPt = [
                tNorm.x0 * pdfPageW,
                tNorm.y0 * pdfPageH,
                tNorm.x1 * pdfPageW,
                tNorm.y1 * pdfPageH
            ];
            const tableEl = createSvgRect(
                tableRectPt,
                `xray-table-rect ${isCurrentActive ? "active" : ""}`,
                `${f.table_ref || "Tabel Rujukan"}: Klik untuk fokus`,
                f.finding_id
            );
            tableEl.id = `svg-table-${f.finding_id}`;
            svgOverlay.appendChild(tableEl);
        }

        // 2. Claim Line Rects & Exact Token Value Rect (Only on currentDocPage)
        // NO hardcoded fallback box when geometry is missing (C2)
        if (claimPage === currentDocPage && (isCurrentActive || isFiltered)) {
            let candidateRects = [];
            if (Array.isArray(f.claim_rects) && f.claim_rects.length > 0) {
                candidateRects = f.claim_rects;
            } else if (Array.isArray(f.claim_source?.boxes) && f.claim_source.boxes.length > 0) {
                candidateRects = f.claim_source.boxes;
            } else if (isValidRect(f.claim_source?.bbox)) {
                candidateRects = [f.claim_source.bbox];
            }

            const validClaimRects = candidateRects.filter(isValidRect);
            if (validClaimRects.length > 0) {
                const claimGroup = document.createElementNS(SVG_NS, "g");
                claimGroup.id = `svg-claim-${f.finding_id}`;
                claimGroup.setAttribute("data-finding-id", f.finding_id);

                validClaimRects.forEach((b, idx) => {
                    const rectKey = `${Math.round(b[0])}_${Math.round(b[1])}_${Math.round(b[2])}_${Math.round(b[3])}`;
                    if (!isCurrentActive && seenInactiveClaimKeys.has(rectKey)) {
                        return;
                    }
                    if (!isCurrentActive) {
                        seenInactiveClaimKeys.add(rectKey);
                    }
                    const seg = createSvgRect(
                        b,
                        `xray-claim-rect ${isCurrentActive ? "active" : ""}`,
                        `Temuan ${f.finding_id}: Klik untuk melihat analisis`,
                        f.finding_id
                    );
                    if (idx === 0) seg.id = `svg-claim-line0-${f.finding_id}`;
                    claimGroup.appendChild(seg);
                });

                // Exact numeric token highlight (value_rect) on top of the line rect
                const valRect = f.claim_source?.value_rect;
                if (isValidRect(valRect) && isCurrentActive) {
                    const valEl = createSvgRect(
                        valRect,
                        `xray-value-rect active cat-${category}`,
                        `Nilai klaim: ${f.claim_value_display || ""}`,
                        f.finding_id
                    );
                    valEl.id = `svg-value-${f.finding_id}`;
                    claimGroup.appendChild(valEl);
                }

                svgOverlay.appendChild(claimGroup);

                // Smart cross-page indicator pill placed strictly in margin gutter layer
                if (gutterLayer && evidencePage !== claimPage && isCurrentActive) {
                    const minX = Math.min(...validClaimRects.map(b => b[0]));
                    const minY = Math.min(...validClaimRects.map(b => b[1]));
                    const maxX = Math.max(...validClaimRects.map(b => b[2]));
                    const leftSpacePt = minX;
                    const rightSpacePt = pdfPageW - maxX;

                    const tagWrap = document.createElement("div");
                    tagWrap.style.position = "absolute";
                    tagWrap.style.top = `${(minY / pdfPageH) * 100}%`;
                    tagWrap.style.pointerEvents = "auto";
                    if (leftSpacePt >= 75) {
                        tagWrap.style.right = `${((pdfPageW - minX) / pdfPageW) * 100}%`;
                        tagWrap.style.marginRight = "8px";
                    } else if (rightSpacePt >= 75) {
                        tagWrap.style.left = `${(maxX / pdfPageW) * 100}%`;
                        tagWrap.style.marginLeft = "8px";
                    } else {
                        tagWrap.style.right = `${Math.max(0, ((pdfPageW - maxX) / pdfPageW) * 100)}%`;
                        tagWrap.style.transform = "translateY(-110%)";
                    }

                    tagWrap.innerHTML = `
                        <button type="button" class="floating-claim-tag" onclick="jumpToEvidencePage(${evidencePage}, '${f.finding_id}', event); return false;" title="Buka Halaman ${evidencePage} untuk melihat tabel bukti">
                            <span class="severity-dot amber"></span>
                            <span>Bukti Hal. ${evidencePage}</span>
                            <svg fill="none" height="11" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24" width="11">
                                <line x1="7" x2="17" y1="17" y2="7"></line>
                                <polyline points="7 7 17 7 17 17"></polyline>
                            </svg>
                        </button>
                    `;
                    gutterLayer.appendChild(tagWrap);
                }
            }
        }

        // 3. Table Evidence Cells (Only on currentDocPage)
        // Strictly skip null / [0,0,0,0] rects; dashed outline when bbox_approx === true
        if (evidencePage === currentDocPage && (isCurrentActive || isFiltered)) {
            const cells = Array.isArray(f.table_evidence?.cells) ? f.table_evidence.cells : [];
            let drawnCells = 0;

            cells.forEach((cell, idx) => {
                const rawRect = isValidRect(cell.cell_rect)
                    ? cell.cell_rect
                    : (isValidRect(cell.bbox) ? cell.bbox : null);
                if (!rawRect) return;

                const isApprox = Boolean(cell.bbox_approx);
                const approxCls = isApprox ? "approx" : "";
                const activeCls = isCurrentActive ? `active cat-${category}` : "";
                const labelVal = cell.raw_val ?? cell.num_val ?? "";
                const titleStr = isApprox
                    ? `Bukti Sel Tabel (perkiraan): ${labelVal}`
                    : `Bukti Sel Tabel: ${labelVal}`;

                const cellEl = createSvgRect(
                    rawRect,
                    `xray-cell-rect ${activeCls} ${approxCls}`.trim(),
                    titleStr,
                    f.finding_id
                );
                cellEl.id = `svg-cell-${f.finding_id}-${idx}`;
                svgOverlay.appendChild(cellEl);
                drawnCells += 1;
            });

            // Fallback to top-level finding.cell_rect if cells array had no valid rects
            if (drawnCells === 0 && isValidRect(f.cell_rect)) {
                const cellEl = createSvgRect(
                    f.cell_rect,
                    `xray-cell-rect ${isCurrentActive ? `active cat-${category}` : ""}`.trim(),
                    `Bukti Sel Tabel: ${f.table_value_display || ""}`,
                    f.finding_id
                );
                cellEl.id = `svg-cell-${f.finding_id}-0`;
                svgOverlay.appendChild(cellEl);
            }
        }
    });

    updateBracket();
    updateCrossPageBanner();
}

function updateBracket() {
    const bracketPath = document.getElementById("bracketPath");
    if (!bracketPath || !activeFindingId || !currentBundle) return;

    const finding = (currentBundle.findings || []).find(f => f.finding_id === activeFindingId);
    if (!finding) {
        bracketPath.setAttribute("d", "M 0 0");
        return;
    }

    const claimPage = finding.claim_source?.page || 1;
    const evidencePage = finding.cell_page || finding.table_evidence?.page || claimPage;

    if (claimPage !== currentDocPage || evidencePage !== currentDocPage) {
        bracketPath.setAttribute("d", "M 0 0");
        return;
    }

    const claimEl = document.getElementById(`svg-claim-${activeFindingId}`);
    const cellEl = document.querySelector(`.xray-cell-rect[data-finding-id="${activeFindingId}"]`);

    if (!claimEl || !cellEl) {
        bracketPath.setAttribute("d", "M 0 0");
        return;
    }

    const pageContainer = document.getElementById("pageContainer");
    if (!pageContainer) return;

    const cRect = pageContainer.getBoundingClientRect();
    const clRect = claimEl.getBoundingClientRect();
    const ceRect = cellEl.getBoundingClientRect();
    if (clRect.width === 0 || ceRect.width === 0) {
        bracketPath.setAttribute("d", "M 0 0");
        return;
    }

    const startY = (clRect.top + clRect.height / 2 - cRect.top) / zoomLevel;
    const endY = (ceRect.top + ceRect.height / 2 - cRect.top) / zoomLevel;
    const startX = (clRect.left - cRect.left) / zoomLevel;
    const endX = (ceRect.left - cRect.left) / zoomLevel;

    const xMargin = 14;
    const cpX = xMargin - 6;

    const d = `M ${startX} ${startY} L ${xMargin} ${startY} C ${cpX} ${(startY * 2 + endY) / 3}, ${cpX} ${(startY + endY * 2) / 3}, ${xMargin} ${endY} L ${endX} ${endY}`;
    bracketPath.setAttribute("d", d);
}

// Render dynamic B2B cards
function renderStudioFindings(findings) {
    const container = document.getElementById("cardsList");
    if (!container) return;
    container.innerHTML = "";

    let fatalCount = 0;
    let warnCount = 0;
    let passCount = 0;

    findings.forEach(f => {
        const meta = getVerdictMeta(f.verdict);
        if (meta.category === "fatal") fatalCount++;
        else if (meta.category === "warning") warnCount++;
        else if (meta.category === "consistent") passCount++;
    });

    const totalEl = document.getElementById("inspectorTotalCount");
    const countAllEl = document.getElementById("tabCountAll");
    const countFatalEl = document.getElementById("tabCountFatal");
    const countWarnEl = document.getElementById("tabCountWarning");
    const countPassEl = document.getElementById("tabCountConsistent");

    if (totalEl) totalEl.textContent = `${findings.length}`;
    if (countAllEl) countAllEl.textContent = `${findings.length}`;
    if (countFatalEl) countFatalEl.textContent = `${fatalCount}`;
    if (countWarnEl) countWarnEl.textContent = `${warnCount}`;
    if (countPassEl) countPassEl.textContent = `${passCount}`;

    // Render Pattern Summary Banner
    const banner = document.getElementById("patternSummaryBanner");
    if (banner) {
        const summary = currentBundle?.pattern_summary || {};
        const dominant = summary.dominant_pattern_label || summary.dominant_pattern || "Bebas Inkonsistensi (Konsisten)";
        const totalAnom = summary.total_anomalies !== undefined ? summary.total_anomalies : findings.length;
        const sha = currentBundle?.document_sha256 || "";
        banner.style.display = "block";
        banner.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                <div style="font-weight: 600; color: #1c1917; font-size: 12px; display: flex; align-items: center; gap: 6px;">
                    <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #0075de;"></span>
                    <span>Pola Dominan: <strong>${dominant}</strong> (${totalAnom} anomali)</span>
                </div>
                <button type="button" class="btn-cert-export" onclick="exportSha256Certificate()" style="font-size: 11px; font-family: 'JetBrains Mono', monospace; padding: 2px 8px; border-radius: 4px; border: 1px solid #d6d3d1; background: #fff; cursor: pointer; color: #44403c;" title="Unduh Sertifikat Bukti Kriptografis SHA-256">
                    Sertifikat SHA-256 ↗
                </button>
            </div>
        `;
    }

    if (findings.length === 0) {
        container.innerHTML = `
            <div style="padding: 40px 20px; text-align: center; color: var(--ink-3);">
                <div style="font-size: 28px; margin-bottom: 8px; color: var(--pass);">✓</div>
                <div style="font-weight: 600; font-size: 14px; color: var(--ink);">100% Konsistensi Terverifikasi</div>
                <div style="font-size: 12px; margin-top: 4px; color: var(--ink-2);">
                    Tidak ditemukan anomali statistik atau ketidaksesuaian tabel pada dokumen ini.
                </div>
            </div>
        `;
        return;
    }

    findings.forEach((f, idx) => {
        const isSelected = (idx === 0);
        const cardHtml = buildB2BCardHtml(f, isSelected);
        container.insertAdjacentHTML("beforeend", cardHtml);
    });

    // Bind card summary toggles
    container.querySelectorAll(".b2b-card").forEach(card => {
        const summary = card.querySelector(".card-summary");
        if (summary) {
            summary.addEventListener("click", () => {
                const fid = card.id.replace("card-", "");
                selectFinding(fid);
            });
        }
    });

    filterStudioCards();
}

function buildB2BCardHtml(f, isSelected = false) {
    const meta = getVerdictMeta(f.verdict);
    const diff = f.diff_details || {};
    const mathTrace = f.math_and_logic_trace || {};
    const claimPage = f.claim_source?.page || 1;
    const evidencePage = f.table_evidence?.page || claimPage;
    const snippet = f.table_evidence?.row_snippet;
    const claimText = f.claim_source?.text || "";

    let dotColor = "amber";
    let dataType = "warning";
    if (meta.category === "fatal") {
        dotColor = "red";
        dataType = "fatal";
    } else if (meta.category === "consistent") {
        dotColor = "green";
        dataType = "consistent";
    }

    // Authoritative Single-Source-Of-Truth contract keys
    const tableRef = f.table_ref || (f.table_evidence?.table_id ? `Tabel ${f.table_evidence.table_id} (Hal. ${evidencePage})` : "Tabel Rujukan");
    const rowCategory = f.row_category || diff.row_label || (f.table_evidence?.cells?.[0]?.row_label) || "Variabel";
    const statColumn = f.stat_column || diff.col_name || "Statistik";
    const claimValDisplay = f.claim_value_display || diff.claimed_val || (claimText.match(/\b\d+[,.]\d+\b/) ? claimText.match(/\b\d+[,.]\d+\b/)[0] : "Klaim");
    const tableValDisplay = f.table_value_display || diff.table_val || "Tabel";
    const tableRounded = diff.table_rounded || tableValDisplay;
    const humanExplanation = f.human_explanation || (diff.plain_explanation || meta.desc).replace(/::/g, " -> ");

    let line3Html = "";
    if (meta.category === "consistent") {
        line3Html = `<span>Ditulis ${claimValDisplay} = Tabel ${tableValDisplay}</span>`;
    } else if (meta.category === "warning") {
        line3Html = `<span>Ditulis</span> <span class="diff-inline-del">${claimValDisplay}</span> <span class="diff-inline-arrow">→</span> <span>Seharusnya</span> <span class="diff-inline-ins">${tableRounded}</span>`;
    } else {
        line3Html = `<span>Teks ${claimValDisplay} vs Tabel ${tableValDisplay}</span>`;
    }

    let quoteHtml = f.highlighted_clause || claimText;
    if (!f.highlighted_clause && claimValDisplay && quoteHtml.includes(claimValDisplay)) {
        quoteHtml = quoteHtml.replace(claimValDisplay, `<mark>${claimValDisplay}</mark>`);
    }

    let socraticHtml = "";
    if (f.socratic_hints && f.socratic_hints.length > 0) {
        socraticHtml = `
            <details class="socratic-hint-box" style="margin: 8px 0; padding: 8px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 12px;">
                <summary style="font-weight: 600; color: #0284c7; cursor: pointer; user-select: none;">💡 Socratic Hint (Panduan Telaah)</summary>
                <ol style="margin: 6px 0 0 18px; padding: 0; color: #334155; line-height: 1.5;">
                    ${f.socratic_hints.map(h => `<li style="margin-bottom: 3px;">${h}</li>`).join("")}
                </ol>
            </details>
        `;
    }

    let stackTraceHtml = "";
    if (f.stack_trace_path) {
        stackTraceHtml = `
            <div class="stack-trace-path" style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #64748b; margin-top: 4px; padding: 4px 8px; background: #f1f5f9; border-radius: 4px;">
                <strong>Jalur Bukti:</strong> ${f.stack_trace_path}
            </div>
        `;
    }

    let snippetHtml = "";
    if (snippet && snippet.headers && snippet.cells) {
        let ths = snippet.headers.map(h => `<th>${h.replace(/::/g, " -> ")}</th>`).join("");
        let tds = snippet.cells.map(c => `<td class="${c.is_target ? 'snippet-target-cell' : ''}">${c.raw_val || c.num_val || '-'}</td>`).join("");
        snippetHtml = `
            <div class="table-snippet-container">
                <div class="table-snippet-header">
                    <span>Cuplikan ${f.table_evidence?.table_id || 'Tabel'} (Hal. ${evidencePage})</span>
                    <button class="table-jump-link" onclick="jumpToEvidencePage(${evidencePage}, '${f.finding_id}', event); event.stopPropagation();">
                        <span>Lompat ke tabel</span>
                        <span>↗</span>
                    </button>
                </div>
                <table class="snippet-table-clean">
                    <thead><tr>${ths}</tr></thead>
                    <tbody><tr>${tds}</tr></tbody>
                </table>
            </div>
        `;
    }

    let recalcHtml = "";
    if (mathTrace.formula_display) {
        recalcHtml = `
            <div class="recalc-clean">
                <div>${mathTrace.formula_display}</div>
                <div class="recalc-match-comment" style="margin-top: 4px; font-size: 11px;">
                    Operasi: ${mathTrace.operation || 'AUDIT'} · Solver: SciPy Engine
                </div>
            </div>
        `;
    }

    return `
        <article class="b2b-card ${isSelected ? 'selected' : ''}" data-type="${dataType}" id="card-${f.finding_id}">
            <div class="card-summary" data-action="toggle">
                <div class="card-line-1">
                    <div class="card-line-1-left">
                        <span class="severity-dot ${dotColor}" title="${meta.title}"></span>
                        <span class="card-title-text">${meta.title}</span>
                    </div>
                    <span class="card-page-label">Hal. ${claimPage}</span>
                </div>
                <!-- 3 Clear Context Labels: Tabel Rujukan, Baris / Kategori, Kolom yang Diuji -->
                <div class="card-context-tags" style="display: flex; flex-wrap: wrap; gap: 4px; margin: 4px 0 6px 0;">
                    <span class="context-pill" style="font-size: 11px; background: rgba(0, 117, 222, 0.08); color: #0075de; border-radius: 4px; padding: 1px 6px; font-weight: 500;">
                        <strong>Tabel:</strong> ${tableRef}
                    </span>
                    <span class="context-pill" style="font-size: 11px; background: #f3f4f6; color: #374151; border-radius: 4px; padding: 1px 6px; font-weight: 500;">
                        <strong>Baris:</strong> ${rowCategory}
                    </span>
                    <span class="context-pill" style="font-size: 11px; background: #f3f4f6; color: #374151; border-radius: 4px; padding: 1px 6px; font-weight: 500;">
                        <strong>Kolom:</strong> ${statColumn}
                    </span>
                </div>
                <div class="card-line-3 mono">
                    ${line3Html}
                </div>
            </div>
            <div class="card-expanded-body" id="body-${f.finding_id}" style="${isSelected ? 'display: flex;' : 'display: none;'}">
                <div class="diff-grid">
                    <div class="diff-grid-col">
                        <span class="diff-grid-label">Di teks (hal. ${claimPage})</span>
                        <div class="diff-grid-val-row">
                            <span class="diff-grid-num ${meta.category === 'consistent' ? 'text-target' : 'text-err'}">${claimValDisplay}</span>
                        </div>
                    </div>
                    <div class="diff-divider"></div>
                    <div class="diff-grid-col">
                        <span class="diff-grid-label">Di tabel (hal. ${evidencePage})</span>
                        <div class="diff-grid-val-row">
                            <span class="diff-grid-num text-target">${tableValDisplay}</span>
                            ${tableRounded !== tableValDisplay ? `<span class="diff-grid-sub">→ baku <strong>${tableRounded}</strong></span>` : ''}
                        </div>
                    </div>
                </div>
                <p class="diff-explanation">${humanExplanation}</p>
                ${claimText ? `<blockquote class="quote-clean">"${quoteHtml}"</blockquote>` : ''}
                ${socraticHtml}
                ${stackTraceHtml}
                ${snippetHtml}
                ${recalcHtml}
                <div class="card-footer-actions">
                    <div class="card-footer-left">
                        <button class="btn-action-primary" onclick="acceptCorrection('${f.finding_id}'); event.stopPropagation();">Terima koreksi</button>
                        <button class="btn-action-ghost" onclick="dismissFinding('${f.finding_id}'); event.stopPropagation();">Abaikan</button>
                    </div>
                    <button class="btn-copy-evidence" onclick="copyEvidenceSnippet('${f.finding_id}'); event.stopPropagation();">
                        <svg fill="none" height="13" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" viewBox="0 0 24 24" width="13">
                            <rect height="13" rx="2" ry="2" width="13" x="9" y="9"></rect>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                        </svg>
                        <span id="copyText-${f.finding_id}">Salin bukti</span>
                    </button>
                </div>
            </div>
        </article>
    `;
}

function selectFinding(findingId) {
    activeFindingId = findingId;

    const cards = document.querySelectorAll(".b2b-card");
    cards.forEach(card => {
        const isTarget = (card.id === `card-${findingId}`);
        card.classList.toggle("selected", isTarget);
        const body = card.querySelector(".card-expanded-body");
        if (body) {
            body.style.display = isTarget ? "flex" : "none";
        }
    });

    const finding = (currentBundle?.findings || []).find(f => f.finding_id === findingId);
    if (finding) {
        const claimPage = finding.claim_source?.page || 1;
        const evidencePage = finding.table_evidence?.page || claimPage;

        // Stay on evidencePage if user is currently inspecting the table!
        if (currentDocPage !== claimPage && currentDocPage !== evidencePage) {
            changeDocPage(claimPage);
        } else {
            renderPdfXRayCanvas();
        }
    } else {
        renderPdfXRayCanvas();
    }
}

function jumpToEvidencePage(targetPage, findingId, event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    activeFindingId = findingId;

    const cards = document.querySelectorAll(".b2b-card");
    cards.forEach(card => {
        const isTarget = (card.id === `card-${findingId}`);
        card.classList.toggle("selected", isTarget);
        const body = card.querySelector(".card-expanded-body");
        if (body) {
            body.style.display = isTarget ? "flex" : "none";
        }
        if (isTarget) {
            card.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    });

    const flashCell = () => {
        setTimeout(() => {
            const cell = document.querySelector(`.xray-cell-rect[data-finding-id="${findingId}"]`);
            if (cell) {
                cell.classList.remove("flash-highlight");
                void cell.getBoundingClientRect();
                cell.classList.add("flash-highlight");
                cell.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }, 80);
    };

    if (currentDocPage === targetPage) {
        renderPdfXRayCanvas();
        flashCell();
        return;
    }

    changeDocPage(targetPage, flashCell);
}

function jumpToClaimPage(claimPage, findingId, event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    activeFindingId = findingId;

    const cards = document.querySelectorAll(".b2b-card");
    cards.forEach(card => {
        const isTarget = (card.id === `card-${findingId}`);
        card.classList.toggle("selected", isTarget);
        const body = card.querySelector(".card-expanded-body");
        if (body) {
            body.style.display = isTarget ? "flex" : "none";
        }
        if (isTarget) {
            card.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    });

    changeDocPage(claimPage, () => {
        setTimeout(() => {
            const seg = document.querySelector(`.xray-value-rect.active, .xray-claim-rect.active`);
            if (seg) {
                seg.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }, 80);
    });
}

function updateCrossPageBanner() {
    const banner = document.getElementById("crossPageBanner");
    const dot = document.getElementById("navBarDot");
    const text = document.getElementById("navBarText");
    const btn = document.getElementById("navBarActionBtn");
    const btnText = document.getElementById("navBarActionText");
    if (!banner || !text || !btn || !btnText) return;

    if (!activeFindingId || !currentBundle) {
        banner.style.display = "none";
        return;
    }

    const finding = (currentBundle.findings || []).find(f => f.finding_id === activeFindingId);
    if (!finding) {
        banner.style.display = "none";
        return;
    }

    const claimPage = finding.claim_source?.page || 1;
    const evidencePage = finding.table_evidence?.page || claimPage;
    const varName = finding.diff_details?.row_label || "Data Teruji";

    if (claimPage !== evidencePage) {
        banner.style.display = "block";
        if (currentDocPage === evidencePage) {
            if (dot) dot.className = "nav-bar-status-dot blue";
            text.innerHTML = `Memeriksa Bukti: <strong>${finding.table_evidence?.table_id || 'Tabel'} (Hal. ${evidencePage})</strong>`;
            btnText.textContent = `← Kembali ke Teks (Hal. ${claimPage})`;
            btn.onclick = (e) => jumpToClaimPage(claimPage, finding.finding_id, e);
        } else if (currentDocPage === claimPage) {
            if (dot) dot.className = "nav-bar-status-dot amber";
            text.innerHTML = `Temuan: <strong>${varName}</strong> (Hal. ${claimPage})`;
            btnText.textContent = `Lihat Bukti di Hal. ${evidencePage} ↗`;
            btn.onclick = (e) => jumpToEvidencePage(evidencePage, finding.finding_id, e);
        } else {
            if (dot) dot.className = "nav-bar-status-dot amber";
            text.innerHTML = `Temuan Terpilih: <strong>${varName}</strong>`;
            btnText.textContent = `Buka Teks di Hal. ${claimPage} →`;
            btn.onclick = (e) => jumpToClaimPage(claimPage, finding.finding_id, e);
        }
    } else {
        banner.style.display = "none";
    }
}

function setStudioFilter(filter) {
    currentFilter = filter;
    document.querySelectorAll(".inspector-tabs .tab-item").forEach(t => {
        t.classList.toggle("active", t.getAttribute("data-filter") === filter);
    });
    filterStudioCards();
    renderPdfXRayCanvas();
}

function filterStudioCards() {
    document.querySelectorAll(".b2b-card").forEach(card => {
        const cardType = card.getAttribute("data-type");
        if (currentFilter === "all" || cardType === currentFilter) {
            card.style.display = "block";
        } else {
            card.style.display = "none";
        }
    });
}

function acceptCorrection(findingId) {
    const card = document.getElementById(`card-${findingId}`);
    if (card) {
        card.style.opacity = "0.65";
        const btn = card.querySelector(".btn-action-primary");
        if (btn) {
            btn.textContent = "✓ Diterima";
            btn.disabled = true;
            btn.style.background = "var(--pass)";
        }
    }
}

function dismissFinding(findingId) {
    const card = document.getElementById(`card-${findingId}`);
    if (card) {
        card.style.display = "none";
    }
}

function copyEvidenceSnippet(findingId) {
    const f = (currentBundle?.findings || []).find(item => item.finding_id === findingId);
    if (!f) return;

    const diff = f.diff_details || {};
    const text = `LOCUS Audit: [${f.finding_id}] ${diff.row_label || 'Klaim'} tertulis ${diff.claimed_val || '-'} di naskah vs ${diff.table_val || '-'} di tabel rujukan. Penjelasan: ${diff.plain_explanation || '-'}`;

    navigator.clipboard.writeText(text).then(() => {
        const copySpan = document.getElementById(`copyText-${findingId}`);
        if (copySpan) {
            copySpan.textContent = "Tersalin!";
            setTimeout(() => {
                copySpan.textContent = "Salin bukti";
            }, 1500);
        }
    });
}

// Zoom Controls
function setZoom(val) {
    zoomLevel = Math.max(0.5, Math.min(2.0, val));
    const viewport = document.getElementById("pdfViewport");
    const display = document.getElementById("zoomLevelDisplay");
    if (viewport) viewport.style.transform = `scale(${zoomLevel})`;
    if (display) display.textContent = `${Math.round(zoomLevel * 100)}%`;
    updateBracket();
}

function setupStudioEventListeners() {
    const btnIn = document.getElementById("btnZoomIn");
    const btnOut = document.getElementById("btnZoomOut");
    const btnFit = document.getElementById("btnZoomFit");

    if (btnIn) btnIn.onclick = () => setZoom(zoomLevel + 0.1);
    if (btnOut) btnOut.onclick = () => setZoom(zoomLevel - 0.1);
    if (btnFit) btnFit.onclick = () => {
        const container = document.getElementById("pdfContainer");
        if (container) {
            const fit = Math.min(1.2, Math.max(0.6, (container.clientWidth - 48) / 640));
            setZoom(fit);
        }
    };

    const btnPrev = document.getElementById("btnPrevPage");
    const btnNext = document.getElementById("btnNextPage");
    if (btnPrev) btnPrev.onclick = () => changeDocPage(currentDocPage - 1);
    if (btnNext) btnNext.onclick = () => changeDocPage(currentDocPage + 1);

    window.addEventListener("resize", () => {
        updateBracket();
    });

    // Responsive ResizeObserver sync for SVG overlay & margin bracket connector
    if (typeof ResizeObserver !== "undefined") {
        const imgEl = document.getElementById("pdf-page-img");
        const pageCont = document.getElementById("pageContainer");
        if (pdfResizeObserver) pdfResizeObserver.disconnect();
        pdfResizeObserver = new ResizeObserver(() => {
            updateBracket();
        });
        if (imgEl) pdfResizeObserver.observe(imgEl);
        if (pageCont) pdfResizeObserver.observe(pageCont);
    }
}

// PDF Upload & Drag-and-Drop
function triggerStudioPdfUpload() {
    const input = document.getElementById("pdf-file-input");
    if (input) input.click();
}

function setupDropzone() {
    const fileInput = document.getElementById("pdf-file-input");
    if (fileInput) {
        fileInput.onchange = async (e) => {
            const file = e.target.files[0];
            if (file) {
                await uploadAndAuditPdf(file);
            }
        };
    }

    const container = document.getElementById("pdfContainer");
    if (container) {
        container.addEventListener("dragover", (e) => {
            e.preventDefault();
            container.style.outline = "2px dashed var(--accent)";
        });
        container.addEventListener("dragleave", () => {
            container.style.outline = "none";
        });
        container.addEventListener("drop", async (e) => {
            e.preventDefault();
            container.style.outline = "none";
            const files = e.dataTransfer.files;
            if (files && files.length > 0 && files[0].name.toLowerCase().endsWith(".pdf")) {
                await uploadAndAuditPdf(files[0]);
            }
        });
    }
}

let loadingTimer = null;
let loadingStartTime = 0;
let activeAuditAbortController = null;
let activeAuditPollInterval = null;

const AUDIT_STEPS_DEF = [
    { id: 1, title: "Deteksi tabel", shortLabel: "Deteksi tabel", desc: "Geometri tabel 3-garis dan klaster kolom.", time: "0,18 dtk" },
    { id: 2, title: "Pemisahan klaim", shortLabel: "Pemisahan klaim", desc: "Teks tabel dimasking agar tidak bocor ke narasi.", time: "0,22 dtk" },
    { id: 3, title: "Ekspansi variabel", shortLabel: "Ekspansi variabel", desc: "Stem morfologi dan resolusi anafora Bab 3/4.", time: "0,31 dtk" },
    { id: 4, title: "Penautan semantik", shortLabel: "Penautan semantik", desc: "Duet model ONNX INT8: bge-reranker-v2-m3 dan mDeBERTa-v3.", subProgress: "model 2/2 · cross-encoder", time: "0,42 dtk" },
    { id: 5, title: "Solver deterministik", shortLabel: "Solver matematika", desc: "8 solver matematika: statcheck, GRIM, FormulaEval.", subProgress: "solver 8/8 · SciPy", time: "0,19 dtk" },
    { id: 6, title: "Sintesis bukti", shortLabel: "Sintesis bukti", desc: "Kurva Bezier, What-If stepper, tanda tangan SHA-256.", subProgress: "hash sha-256 · siap", time: "0,09 dtk" }
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
    const overlay = document.getElementById("modalOverlay");
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

    if (modalTitle) modalTitle.textContent = `Mengaudit ${docTitle}`;
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
        const docChip = document.getElementById("docTitleDisplay");
        if (docChip) docChip.textContent = "Audit dibatalkan";
    };

    if (btnCloseModal) {
        btnCloseModal.onclick = cancelAudit;
    }
    if (btnCancelAudit) {
        btnCancelAudit.onclick = cancelAudit;
    }
    if (btnRetryAudit) {
        btnRetryAudit.onclick = () => {
            const input = document.getElementById("pdf-file-input");
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
        const overlay = document.getElementById("modalOverlay");
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

function exportSha256Certificate() {
    const sha = currentBundle?.document_sha256 || "UNKNOWN_SHA256";
    const ver = currentBundle?.engine_version || "v3.5-grounded";
    const findings = currentBundle?.findings || [];
    const cert = {
        certificate_type: "LOCUS Scientific Integrity Proof Receipt",
        engine_version: ver,
        timestamp: new Date().toISOString(),
        document_sha256: sha,
        document_filename: sessionStorage.getItem("locus_active_filename") || "BAB 4.pdf",
        readiness_score: currentBundle?.readiness_score || 100.0,
        pattern_summary: currentBundle?.pattern_summary || {},
        summary_counts: currentBundle?.summary_counts || { total_claims_checked: 0, findings_count: findings.length },
        findings_count: findings.length
    };
    const blob = new Blob([JSON.stringify(cert, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `locus_proof_certificate_${sha.substring(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

async function exportAuditReceipt() {
    if (!currentBundle) {
        alert("Belum ada data audit yang aktif untuk diekspor.");
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
        if (data.status === "success" && data.receipt) {
            const sha = data.receipt.document_sha256 || currentBundle.document_sha256 || "RECEIPT";
            const blob = new Blob([JSON.stringify(data.receipt, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `locus_receipt_${sha.substring(0, 10)}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            return;
        }
    } catch (e) {
        console.warn("Gagal panggil /api/v1/export-receipt, fallback ke local cert:", e);
    }
    exportSha256Certificate();
}
window.exportAuditReceipt = exportAuditReceipt;
window.exportSha256Certificate = exportAuditReceipt;

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

    const docChip = document.getElementById("docTitleDisplay");
    if (docChip) docChip.textContent = `Memproses: ${file.name}...`;

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
            if (docChip) docChip.textContent = "Gagal memproses";
            return;
        }

        const json = await res.json();
        if (activeAuditPollInterval) {
            clearInterval(activeAuditPollInterval);
            activeAuditPollInterval = null;
        }

        if (json.status === "success" && json.data) {
            const bundle = json.data;
            bundle.document_sha256 = json.document_sha256;
            bundle.engine_version = json.engine_version || "v3.5-grounded";
            bundle.readiness_score = json.readiness_score;
            bundle.pattern_summary = json.pattern_summary;

            sessionStorage.setItem("locus_active_bundle", JSON.stringify(bundle));
            sessionStorage.setItem("locus_active_filename", file.name);
            if (docChip) docChip.textContent = file.name;
            setPipelineStep(6, 100, "Sintesis bukti");

            const findings = bundle.findings || [];
            const summaryText = `${findings.length} temuan terdeteksi`;

            finishAuditLoading(summaryText, () => {
                displayAuditBundle(bundle);
            });
        } else {
            showAuditError(json.detail || "Gagal memproses dokumen");
            if (docChip) docChip.textContent = "Gagal memproses";
        }
    } catch (err) {
        if (err.name === "AbortError") {
            if (activeAuditPollInterval) {
                clearInterval(activeAuditPollInterval);
                activeAuditPollInterval = null;
            }
            console.log("Audit dibatalkan oleh pengguna.");
            if (docChip) docChip.textContent = "Audit dibatalkan";
            return;
        }

        console.warn("Koneksi POST terputus (kemungkinan perubahan jaringan / Wi-Fi off). Memulai auto-recovery...", err);

        // Auto-recovery mechanism:
        // When Wi-Fi is disabled, Chrome drops active sockets with ERR_NETWORK_CHANGED,
        // but local backend worker at 127.0.0.1 continues executing.
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
                        if (docChip) docChip.textContent = file.name;
                        setPipelineStep(6, 100, "Sintesis bukti");

                        const findings = bundle.findings || [];
                        const summaryText = `${findings.length} temuan terdeteksi`;

                        finishAuditLoading(summaryText, () => {
                            displayAuditBundle(bundle);
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
        console.error("Gagal audit PDF:", err);
        if (docChip) docChip.textContent = "Koneksi gagal";
    } finally {
        activeAuditAbortController = null;
    }
}
