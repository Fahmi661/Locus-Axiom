import hashlib, json, datetime
from typing import List, Dict, Any

ENGINE_VERSION = "LOCUS-v3.3"

def compute_pdf_sha256(pdf_path: str) -> str:
    h = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def build_audit_chain(pdf_path: str, findings: List[Dict[str, Any]], tables: List[Dict[str, Any]], timestamp: str = None) -> Dict[str, Any]:
    doc_hash = compute_pdf_sha256(pdf_path)
    if not timestamp:
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    chain = []
    for f in findings:
        dd = f.get("diff_details", {})
        te = f.get("table_evidence", {})
        chain.append({
            "finding_id": f.get("finding_id"),
            "verdict": f.get("verdict"),
            "variable": dd.get("row_label", ""),
            "stat_type": dd.get("col_name", ""),
            "claimed_val": dd.get("claimed_val", ""),
            "table_val": dd.get("table_val", ""),
            "cell_coordinate": {
                "table_id": te.get("table_id", ""),
                "row": dd.get("row_label", ""),
                "col": dd.get("col_name", "")
            },
            "rounding_bounds": dd.get("diff", None),
            "page": f.get("claim_source", {}).get("page", None)
        })
    return {
        "document_sha256": doc_hash,
        "audit_timestamp": timestamp,
        "engine_version": ENGINE_VERSION,
        "total_findings": len(findings),
        "findings_chain": chain
    }
