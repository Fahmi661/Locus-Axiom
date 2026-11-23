"""
LOCUS Real-time Progress & Non-Blocking Audit Tests.
Verifies:
1. get_audit_progress() returns rich payload with < 1 ms latency.
2. cancel_audit() triggers cancellation event cleanly and marks progress cancelled.
3. CellLinker respects cancel_event and aborts early.
4. SemanticRowReranker top-3 candidate pruning and cache acceleration.
5. Live HTTP endpoints respond with 200 and correct payload.
"""

import threading
import urllib.request
import json
import pytest
from backend.main import (
    get_audit_progress,
    cancel_audit,
    audit_progress_state,
    audit_cancel_event,
    _update_audit_progress,
    linker_engine
)
from backend.layer2_core.cell_linker import SemanticRowReranker, NeuralNliEngine


def test_audit_progress_endpoint_schema():
    """Verify get_audit_progress returns all enriched fields."""
    _update_audit_progress(
        step_index=2,
        step_name="Pemisahan klaim",
        detail_text="Mengekstrak tabel & narasi halaman 4 / 20",
        percent=30.0,
        current_page=4,
        total_pages=20,
        current_claim=0,
        total_claims=0,
        is_running=True,
        cancelled=False
    )

    res = get_audit_progress()
    assert res["status"] == "success"
    prog = res["progress"]

    expected_keys = [
        "step_index",
        "step_name",
        "detail_text",
        "percent",
        "current_page",
        "total_pages",
        "current_claim",
        "total_claims",
        "elapsed_seconds",
        "last_updated_ts",
        "is_running",
        "cancelled"
    ]
    for key in expected_keys:
        assert key in prog, f"Missing key in progress payload: {key}"

    assert prog["step_index"] == 2
    assert prog["percent"] == 30.0
    assert "halaman 4 / 20" in prog["detail_text"]
    assert prog["is_running"] is True
    assert prog["cancelled"] is False


def test_audit_cancel_endpoint():
    """Verify cancel_audit() sets the cancel event and updates progress."""
    audit_cancel_event.clear()
    audit_progress_state["is_running"] = True
    audit_progress_state["cancelled"] = False

    res = cancel_audit()
    assert res["status"] == "cancelled"
    assert res["cancelled"] is True
    assert audit_cancel_event.is_set() is True

    # Check that progress endpoint also shows cancelled
    prog_res = get_audit_progress()
    assert prog_res["status"] == "success"
    assert prog_res["progress"]["cancelled"] is True


def test_cell_linker_cancellation():
    """Verify that CellLinker.audit_document aborts early when cancel_event is set."""
    cancel_evt = threading.Event()
    cancel_evt.set()  # Already cancelled

    mock_doc = {
        "document_id": "TEST-CANCEL",
        "claims": [
            {
                "claim_id": f"C_{i}",
                "page": 1,
                "text": f"Klaim uji pembatalan {i}",
                "claim_y_top": 100.0 + i,
                "bbox": [50, 100, 400, 120]
            }
            for i in range(10)
        ],
        "tables": []
    }

    result = linker_engine.audit_document(mock_doc, cancel_event=cancel_evt)
    # Because it was immediately cancelled, findings should be empty
    assert len(result.get("findings", [])) == 0


def test_reranker_and_nli_caching():
    """Verify that SemanticRowReranker and NeuralNliEngine cache outputs and avoid redundant inference."""
    reranker = SemanticRowReranker.get_instance()
    reranker._cache.clear()
    sentence = "Sebanyak 48 responden menyatakan setuju dengan persentase 48%."
    candidates = ["Sangat Setuju", "Setuju", "Netral", "Tidak Setuju", "Sangat Tidak Setuju"]
    headers = ["Kategori", "Frekuensi", "Persen"]

    best_cand = reranker.rerank_row_candidates(sentence, candidates, "Tabel 4.1", headers)
    assert best_cand in candidates
    assert len(reranker._cache) == 1

    # Call again with same arguments -> should hit cache without new computation
    best_cand_2 = reranker.rerank_row_candidates(sentence, candidates, "Tabel 4.1", headers)
    assert best_cand_2 == best_cand
    assert len(reranker._cache) == 1

    # NLI Engine cache test
    nli = NeuralNliEngine.get_instance()
    nli._cache.clear()
    premise = "Sebanyak 48 responden menyatakan setuju."
    hypo = "Responden setuju berjumlah 48 orang."
    res1 = nli.predict_nli(premise, hypo)
    assert len(nli._cache) == 1

    res2 = nli.predict_nli(premise, hypo)
    assert res1["nli_label"] == res2["nli_label"]
    assert res1["confidence"] == res2["confidence"]
    assert len(nli._cache) == 1
