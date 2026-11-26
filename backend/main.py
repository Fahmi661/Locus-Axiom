"""
LOCUS (Cursor for Scientific Integrity)
Local Offline Neuro-Symbolic Audit Server.
FastAPI backend running at 127.0.0.1:8000.
100% Offline, Zero-PII, Zero-AGPL.
"""

import os
import sys

# Force 100% Offline mode for Hugging Face and ML libraries
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
import json
import time
import shutil
import tempfile
import argparse
import hashlib
import threading
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# Add workspace root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.layer1_perception.pdf_reader import FastPdfReader
from backend.layer2_core.cell_linker import CellLinker
from backend.layer2_core.stat_solvers import (
    StatcheckSolver,
    GuardedGrimSolver,
    GrimmerSolver,
    DebitSolver,
    ConfusionMatrixAndSumAuditor
)
from backend.layer3_export.pii_redactor import PiiRedactor
from backend.layer3_export.revision_builder import RevisionBuilder

app = FastAPI(
    title="LOCUS Engine API",
    description="Offline Neuro-Symbolic Proof Engine for Scientific Table & Text Consistency",
    version="1.0.0"
)

# CORS middleware for local operations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


class NoCacheStaticFiles(StaticFiles):
    """Overrides file_response to strictly enforce fresh assets without browser caching."""
    def file_response(self, *args, **kwargs) -> Response:
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp


# Ensure static directories
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
STATIC_PAGES_DIR = os.path.join(BASE_DIR, "data", "rendered_pages")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_PAGES_DIR, exist_ok=True)

app.mount("/static/pages", StaticFiles(directory=STATIC_PAGES_DIR), name="static_pages")
app.mount("/static/presets", StaticFiles(directory=os.path.join(BASE_DIR, "data", "presets")), name="static_presets")

# Frontend directory mount with NoCacheStaticFiles
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/app", NoCacheStaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


linker_engine = CellLinker()
latest_audit_cache = None

audit_cancel_event = threading.Event()

audit_progress_state = {
    "step_index": 1,
    "step_name": "Siap",
    "detail_text": "Menunggu dokumen...",
    "percent": 0,
    "current_page": 0,
    "total_pages": 1,
    "current_claim": 0,
    "total_claims": 0,
    "elapsed_seconds": 0.0,
    "last_updated_ts": time.time(),
    "is_running": False,
    "cancelled": False
}


class TableBboxNorm(BaseModel):
    page: int
    x0: float
    y0: float
    x1: float
    y1: float


class FindingContractItem(BaseModel):
    finding_id: str
    verdict: str
    severity: str
    table_ref: str
    row_category: str
    stat_column: str
    claim_value_display: str
    table_value_display: str
    highlighted_clause: str
    human_explanation: str
    stack_trace_path: str
    socratic_hints: List[str]
    table_bbox_norm: Optional[TableBboxNorm] = None
    claim_source: Optional[Dict[str, Any]] = None
    table_evidence: Optional[Dict[str, Any]] = None
    diff_details: Optional[Dict[str, Any]] = None
    math_and_logic_trace: Optional[Dict[str, Any]] = None
    pedagogical_prompt: Optional[Dict[str, Any]] = None


class AuditResponse(BaseModel):
    status: str
    engine_version: str = "v3.5-grounded"
    elapsed_seconds: float
    readiness_score: float
    skipped_count: int
    pattern_summary: Dict[str, Any]
    document_sha256: str
    data: Dict[str, Any]


class WhatIfRequest(BaseModel):
    finding_type: Optional[str] = None
    test_type: Optional[str] = "t"
    stat_val: Optional[float] = None
    df1: Optional[float] = None
    df2: Optional[float] = None
    p_reported: Optional[float] = None
    context_text: str = ""
    mean_val: Optional[float] = None
    n_sample: Optional[int] = None
    k_items: int = 1
    polarity: Optional[int] = None
    other_vals: Optional[List[float]] = None


class ExportReceiptRequest(BaseModel):
    proof_bundle: Dict[str, Any]
    redact_pii: bool = True


@app.get("/")
def read_root():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "LOCUS Scientific Integrity Engine is running offline.", "docs": "/docs"}


@app.get("/LOCUS_demo.gif")
def get_locus_demo():
    gif_path = os.path.join(FRONTEND_DIR, "LOCUS_demo.gif")
    if os.path.exists(gif_path):
        return FileResponse(gif_path, media_type="image/gif")
    root_gif = os.path.join(BASE_DIR, "LOCUS_demo.gif")
    if os.path.exists(root_gif):
        return FileResponse(root_gif, media_type="image/gif")
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/api/v1/latest-audit")
@app.get("/api/latest-audit")
def get_latest_audit():
    global latest_audit_cache
    if latest_audit_cache and latest_audit_cache.get("bundle"):
        resp = latest_audit_cache.get("response") or {}
        return {
            "status": "success",
            "engine_version": "v3.5-grounded",
            "elapsed_seconds": resp.get("elapsed_seconds", 1.2),
            "readiness_score": resp.get("readiness_score", 95.0),
            "skipped_count": resp.get("skipped_count", 0),
            "pattern_summary": resp.get("pattern_summary", {}),
            "document_sha256": resp.get("document_sha256", ""),
            "data": latest_audit_cache["bundle"],
            "filename": latest_audit_cache.get("filename", "BAB 4.pdf")
        }

    real_file = os.path.join(BASE_DIR, "data", "latest_real_audit.json")
    if os.path.exists(real_file):
        try:
            with open(real_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                latest_audit_cache = d
                resp = d.get("response") or {}
                return {
                    "status": "success",
                    "engine_version": "v3.5-grounded",
                    "elapsed_seconds": resp.get("elapsed_seconds", 1.2),
                    "readiness_score": resp.get("readiness_score", 95.0),
                    "skipped_count": resp.get("skipped_count", 0),
                    "pattern_summary": resp.get("pattern_summary", {}),
                    "document_sha256": resp.get("document_sha256", ""),
                    "data": d.get("bundle"),
                    "filename": d.get("filename", "BAB 4.pdf")
                }
        except Exception:
            pass

    return {"status": "empty"}


@app.get("/api/v1/presets")
def get_presets():
    """
    Returns 3 instant Golden Presets with their precomputed ProofBundles for stage demo (<50 ms).
    """
    presets_file = os.path.join(BASE_DIR, "data", "presets", "presets_precomputed.json")
    if os.path.exists(presets_file):
        with open(presets_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {"status": "success", "presets": data}
    return {"status": "error", "message": "Presets not found. Run generate_presets.py first."}


@app.get("/api/v1/audit/progress")
@app.get("/api/audit/progress")
def get_audit_progress():
    """Returns real-time server-side progress of ongoing PDF audit."""
    return {"status": "success", "progress": audit_progress_state}


@app.post("/api/v1/audit/cancel")
@app.post("/api/audit/cancel")
def cancel_audit():
    """Cancels an ongoing PDF audit in realtime."""
    global audit_cancel_event, audit_progress_state
    audit_cancel_event.set()
    audit_progress_state.update({
        "is_running": False,
        "cancelled": True,
        "detail_text": "Audit dibatalkan oleh pengguna",
        "last_updated_ts": time.time()
    })
    return {"status": "cancelled", "cancelled": True, "message": "Audit cancellation requested"}


def _update_audit_progress(
    step_index: int = 1,
    step_name: str = "Deteksi tabel",
    detail_text: Optional[str] = None,
    percent: float = 5.0,
    current_page: int = 0,
    total_pages: int = 1,
    current_claim: int = 0,
    total_claims: int = 0,
    elapsed_seconds: float = 0.0,
    is_running: bool = True,
    cancelled: bool = False
) -> None:
    audit_progress_state.update({
        "step_index": step_index,
        "step_name": step_name,
        "detail_text": detail_text or f"{step_name} (Halaman {current_page}/{total_pages})",
        "percent": percent,
        "current_page": current_page,
        "total_pages": total_pages,
        "current_claim": current_claim,
        "total_claims": total_claims,
        "elapsed_seconds": elapsed_seconds,
        "last_updated_ts": time.time(),
        "is_running": is_running,
        "cancelled": cancelled
    })


async def _execute_audit(file: UploadFile) -> Dict[str, Any]:
    global latest_audit_cache, audit_progress_state, audit_cancel_event
    start_time = time.perf_counter()
    audit_cancel_event.clear()
    filename = file.filename or "uploaded.pdf"
    unique_id = f"DOC-{int(time.time())}"
    doc_upload_dir = os.path.join(STATIC_PAGES_DIR, unique_id)
    os.makedirs(doc_upload_dir, exist_ok=True)

    audit_progress_state.update({
        "step_index": 1,
        "step_name": "Deteksi tabel",
        "detail_text": f"Mempersiapkan dokumen {filename}...",
        "percent": 5,
        "current_page": 0,
        "total_pages": 1,
        "current_claim": 0,
        "total_claims": 0,
        "elapsed_seconds": 0.0,
        "last_updated_ts": time.time(),
        "is_running": True,
        "cancelled": False
    })

    pdf_temp_path = os.path.join(UPLOAD_DIR, f"{unique_id}_{filename}")
    with open(pdf_temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    doc_sha256 = hashlib.sha256(content).hexdigest()

    def progress_hook(
        current_page: int,
        total_pages: int,
        step_name: str = "Solver deterministik",
        pct: Optional[int] = None,
        detail_text: Optional[str] = None,
        step_index: Optional[int] = None,
        current_claim: int = 0,
        total_claims: int = 0
    ):
        elapsed = round(time.perf_counter() - start_time, 2)
        calc_pct = pct if pct is not None else int(min(95, 20 + (current_page / max(total_pages, 1)) * 75))
        if step_index is None:
            step_index = 5 if "deterministik" in step_name.lower() else (2 if "ekstrak" in step_name.lower() else 1)
        audit_progress_state.update({
            "step_index": step_index,
            "step_name": step_name,
            "detail_text": detail_text or f"{step_name} (Halaman {current_page}/{total_pages})",
            "percent": calc_pct,
            "current_page": current_page,
            "total_pages": total_pages,
            "current_claim": current_claim,
            "total_claims": total_claims,
            "elapsed_seconds": elapsed,
            "last_updated_ts": time.time(),
            "is_running": True,
            "cancelled": False
        })

    try:
        # Layer 1 Perception (Worker Thread via asyncio.to_thread)
        audit_progress_state.update({
            "step_index": 1,
            "step_name": "Deteksi tabel",
            "detail_text": "Merender halaman & memindai tabel...",
            "percent": 10
        })
        doc_graph = await asyncio.to_thread(
            FastPdfReader.process_pdf,
            pdf_temp_path,
            output_images_dir=doc_upload_dir,
            progress_callback=progress_hook,
            cancel_event=audit_cancel_event
        )

        if audit_cancel_event.is_set() or doc_graph.get("cancelled"):
            audit_progress_state.update({
                "is_running": False,
                "cancelled": True,
                "detail_text": "Audit dibatalkan oleh pengguna"
            })
            raise HTTPException(status_code=499, detail="Audit dibatalkan oleh pengguna")

        doc_graph["document_id"] = unique_id

        # Layer 2 Core Neuro-Symbolic Audit (Worker Thread via asyncio.to_thread)
        audit_progress_state.update({
            "step_index": 5,
            "step_name": "Solver deterministik",
            "detail_text": "Mengevaluasi solver deterministik...",
            "percent": 50
        })
        bundle = await asyncio.to_thread(
            linker_engine.audit_document,
            doc_graph,
            progress_callback=progress_hook,
            cancel_event=audit_cancel_event
        )

        if audit_cancel_event.is_set():
            audit_progress_state.update({
                "is_running": False,
                "cancelled": True,
                "detail_text": "Audit dibatalkan oleh pengguna"
            })
            raise HTTPException(status_code=499, detail="Audit dibatalkan oleh pengguna")

        elapsed_sec = round(time.perf_counter() - start_time, 3)
        bundle["processing_time_ms"] = round(elapsed_sec * 1000.0, 2)
        bundle["document_sha256"] = doc_sha256

        findings = bundle.get("findings", [])
        skipped_count = bundle.get("summary_counts", {}).get("skip_nei_count", 0)

        # Pattern summary & readiness score
        VERDICT_HUMAN_LABELS = {
            "DIRECT_CELL_CONTRADICTION": "Inkonsistensi Nilai Sel",
            "VALUE_MISMATCH": "Inkonsistensi Nilai Sel",
            "QUAD_TUPLE_VALUE_MISMATCH": "Inkonsistensi Nilai Sel",
            "COLUMN_SWAP_ERROR": "Salah Baca Kolom Tabel",
            "ROW_SUM_MISMATCH": "Ketidakcocokan Jumlah Sampel",
            "TABLE_REFERENCE_TYPO": "Salah Nomor Rujukan Tabel",
            "UNSUPPORTED_SUPERLATIVE": "Klaim Superlatif Tanpa Bukti",
            "CONFUSION_MATRIX_SUM_MISMATCH": "Ketidakcocokan Jumlah Matriks",
            "WARN_TRUNCATION_ROUNDING": "Pemotongan Desimal Tanpa Pembulatan",
            "WARN_ROUNDING": "Variasi Pembulatan Desimal",
            "DECISION_FLIP_ERROR": "Pembalik Keputusan Signifikansi",
            "POLARITY_INVERSION_ERROR": "Inversi Polaritas Metrik",
            "PREREQUISITE_LOGIC_INVERSION": "Logika Uji Normalitas Terbalik",
            "INLINE_FORMULA_NARRATIVE_CONTRADICTION": "Inkonsistensi Nilai Rumus",
            "GRIM_INCONSISTENCY": "Inkonsistensi Rata-Rata (GRIM)",
            "SPRITE_INCONSISTENCY": "Inkonsistensi Varians (SPRITE)",
        }

        anomaly_findings = [f for f in findings if f.get("verdict") != "PASS_EXACT_MATCH"]
        pattern_counts: Dict[str, int] = {}
        for f in anomaly_findings:
            v = f.get("verdict", "OTHER")
            pattern_counts[v] = pattern_counts.get(v, 0) + 1

        if pattern_counts:
            dominant_raw = max(pattern_counts.items(), key=lambda x: x[1])[0]
            dominant_label = VERDICT_HUMAN_LABELS.get(dominant_raw, dominant_raw)
        else:
            dominant_raw = "NONE"
            dominant_label = "Bebas Inkonsistensi (Konsisten)"

        pattern_summary = {
            "total_anomalies": len(anomaly_findings),
            "counts_by_verdict": pattern_counts,
            "dominant_pattern_code": dominant_raw,
            "dominant_pattern": dominant_label,
            "dominant_pattern_label": dominant_label
        }

        readiness_score = max(15.0, round(100.0 - (len(anomaly_findings) * 8.5), 1)) if anomaly_findings else 100.0

        audit_progress_state.update({
            "step_index": 6,
            "step_name": "Sintesis bukti",
            "detail_text": "Audit selesai",
            "percent": 100,
            "elapsed_seconds": elapsed_sec,
            "is_running": False,
            "cancelled": False
        })

        response_payload = {
            "status": "success",
            "engine_version": "v3.5-grounded",
            "elapsed_seconds": elapsed_sec,
            "readiness_score": readiness_score,
            "skipped_count": skipped_count,
            "pattern_summary": pattern_summary,
            "document_sha256": doc_sha256,
            "data": bundle
        }

        latest_audit_cache = {"bundle": bundle, "filename": filename, "response": response_payload}

        real_file = os.path.join(BASE_DIR, "data", "latest_real_audit.json")
        try:
            with open(real_file, "w", encoding="utf-8") as f:
                json.dump({"bundle": bundle, "filename": filename, "response": response_payload}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return response_payload
    except HTTPException:
        audit_progress_state["is_running"] = False
        raise
    except Exception as e:
        audit_progress_state["is_running"] = False
        raise HTTPException(status_code=500, detail=f"Gagal melakukan audit PDF: {str(e)}")


@app.post("/api/v1/audit", response_model=AuditResponse)
async def audit_pdf_v1(file: UploadFile = File(...)):
    """Uploads PDF and executes authoritative v3.4-synced audit (v1 route)."""
    return await _execute_audit(file)


@app.post("/api/audit", response_model=AuditResponse)
async def audit_pdf_root(file: UploadFile = File(...)):
    """Uploads PDF and executes authoritative v3.4-synced audit (root API route)."""
    return await _execute_audit(file)


@app.post("/api/v1/what-if")
def calculate_what_if(req: WhatIfRequest):
    """
    Live What-If Cell Stepper: recalculates p-values, polarities, or GRIM feasibility
    in <5 ms when the user steps a cell value by ±0.01.
    """
    t0 = time.perf_counter()

    # Branch 1: Polarity Inversion What-If (e.g. RMSE, MAE, Error metrics)
    if req.finding_type == "POLARITY_INVERSION" or (req.polarity is not None and req.other_vals):
        val = req.stat_val if req.stat_val is not None else 0.92
        others = req.other_vals or [0.41, 0.57]
        is_lower_better = (req.polarity == -1)

        if is_lower_better:
            is_best = val < min(others)
            best_other = min(others)
        else:
            is_best = val > max(others)
            best_other = max(others)

        if is_best:
            verdict = "PASS"
            status_text = f"Klaim Benar: Nilai {val:.2f} adalah yang terbaik dibandingkan model lain ({', '.join(f'{x:.2f}' for x in others)})"
        else:
            verdict = "POLARITY_INVERSION_ERROR"
            status_text = f"Inkonsisten: Nilai {val:.2f} kalah unggul dibandingkan model lain (terbaik: {best_other:.2f})"

        res = {
            "verdict": verdict,
            "status_text": status_text,
            "current_val": val,
            "is_best": is_best
        }

    # Branch 2: Normality or Prerequisite Inversion What-If
    elif req.finding_type == "PREREQUISITE_INVERSION" or req.test_type == "normality":
        val = req.stat_val if req.stat_val is not None else 0.018
        if val >= 0.05:
            verdict = "PASS"
            status_text = f"Klaim Terbukti: Nilai Sig. ({val:.3f}) >= 0,05 (distribusi normal terpenuhi)"
        else:
            verdict = "PREREQUISITE_INVERSION_ERROR"
            status_text = f"Inkonsisten: Nilai Sig. ({val:.3f}) < 0,05 (distribusi TIDAK normal)"

        res = {
            "verdict": verdict,
            "status_text": status_text,
            "current_val": val,
            "p_val": val
        }

    # Branch 3: GRIM / Integer Arithmetic What-If
    elif req.mean_val is not None and req.n_sample is not None:
        res = GuardedGrimSolver.solve(
            mean_val=req.mean_val,
            n_sample=req.n_sample,
            k_items=req.k_items,
            mean_str=str(req.mean_val)
        )

    # Branch 4: Statcheck Continuous p-value Recalculation
    else:
        stat_v = req.stat_val if req.stat_val is not None else 2.41
        df_1 = req.df1 if req.df1 is not None else 58.0
        p_rep = req.p_reported if req.p_reported is not None else 0.002
        res = StatcheckSolver.solve(
            test_type=req.test_type or "t",
            stat_val=stat_v,
            df1=df_1,
            df2=req.df2,
            p_reported=p_rep,
            stat_str=str(stat_v),
            context_text=req.context_text
        )

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    res["latency_ms"] = round(elapsed_ms, 3)
    return {"status": "success", "result": res}


@app.post("/api/v1/export-receipt")
def export_receipt(req: ExportReceiptRequest):
    """
    Generates a Zero-PII Numerical Consistency Receipt with SHA-256 verification hash.
    """
    receipt = PiiRedactor.generate_consistency_receipt(req.proof_bundle)
    return {"status": "success", "receipt": receipt}


# CLI Batch Audit
def run_cli_batch_audit(folder_path: str, output_json: str, anonymize: bool = True):
    if not os.path.exists(folder_path):
        print(f"Error: Folder {folder_path} does not exist.")
        return

    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    print(f"Auditing batch of {len(pdf_files)} PDFs from {folder_path}...")

    results = []
    total_findings = 0

    for idx, pdf_name in enumerate(pdf_files, 1):
        pdf_p = os.path.join(folder_path, pdf_name)
        doc_graph = FastPdfReader.process_pdf(pdf_p)
        bundle = linker_engine.audit_document(doc_graph)
        if anonymize:
            bundle = PiiRedactor.redact_proof_bundle(bundle)

        findings_count = len(bundle.get("findings", []))
        total_findings += findings_count
        results.append({
            "sample_id": f"SAMPEL-{idx:02d}",
            "file": pdf_name,
            "findings_count": findings_count,
            "summary": bundle.get("summary_counts", {})
        })
        print(f"[{idx}/{len(pdf_files)}] {pdf_name}: {findings_count} temuan inkonsistensi")

    summary_out = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_documents": len(pdf_files),
        "total_inconsistencies_found": total_findings,
        "batch_details": results
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary_out, f, indent=2, ensure_ascii=False)
    print(f"Batch audit summary saved to {output_json}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LOCUS Scientific Integrity Engine")
    parser.add_argument("--batch-audit", help="Run batch audit on folder of PDFs")
    parser.add_argument("--anonymize", action="store_true", help="Redact PII in batch audit")
    parser.add_argument("--out", default="data/audit_summary.json", help="Output path for batch summary")
    parser.add_argument("--port", type=int, default=8000, help="Port for server")

    args = parser.parse_args()

    if args.batch_audit:
        run_cli_batch_audit(args.batch_audit, args.out, args.anonymize)
    else:
        import uvicorn
        print("Starting LOCUS Offline Server at http://127.0.0.1:8000 ...")
        uvicorn.run("backend.main:app", host="127.0.0.1", port=args.port, reload=False)
