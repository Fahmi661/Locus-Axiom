"""
LOCUS v3.5 Model Downloader Script.
Downloads lightweight INT8 quantized ONNX models and tokenizers for 100% offline CPU execution.
Uses huggingface_hub to fetch exact files without downloading heavy FP32 PyTorch weights.
"""

import os
import sys
from pathlib import Path

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    print("Error: huggingface_hub is not installed. Please install it with 'pip install huggingface_hub'.")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "data" / "models"


def download_mdeberta_nli():
    """Download MoritzLaurer/mDeBERTa-v3-base-mnli-xnli INT8 model and tokenizer."""
    repo_id = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
    target_dir = MODELS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "onnx").mkdir(parents=True, exist_ok=True)

    print(f"\n--- Checking/Downloading mDeBERTa-v3 NLI Model from {repo_id} ---")
    files_to_download = [
        ("onnx/model_quantized.onnx", target_dir / "onnx" / "model_quantized.onnx"),
        ("tokenizer.json", target_dir / "tokenizer.json"),
    ]

    for filename, local_path in files_to_download:
        if local_path.exists() and local_path.stat().st_size > 1000:
            print(f"[OK] Already exists: {local_path} ({local_path.stat().st_size / (1024*1024):.1f} MB)")
            continue

        print(f"[DOWNLOADING] {filename} -> {local_path} ...")
        try:
            downloaded = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=str(target_dir),
                local_dir_use_symlinks=False
            )
            print(f"[SUCCESS] Downloaded: {downloaded}")
        except Exception as e:
            print(f"[WARNING] Could not download {filename} from {repo_id}: {e}")


def download_bge_reranker():
    """Download BGE Reranker v2-m3 INT8 ONNX model, tokenizer, and config."""
    target_dir = MODELS_DIR / "bge-reranker-v2-m3"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "onnx").mkdir(parents=True, exist_ok=True)

    repos = [
        ("pamin-labs/bge-reranker-v2-m3-sq-int8-onnx", "onnx/model_int8.onnx"),
        ("onnx-community/bge-reranker-v2-m3-ONNX", "onnx/model_quantized.onnx"),
    ]

    print("\n--- Checking/Downloading BGE Reranker v2-m3 INT8 ONNX Model ---")
    
    # Check if target model file already exists
    model_dest = target_dir / "onnx" / "model_int8.onnx"
    if model_dest.exists() and model_dest.stat().st_size > 1000:
        print(f"[OK] Already exists: {model_dest} ({model_dest.stat().st_size / (1024*1024):.1f} MB)")
    else:
        downloaded_model = False
        for repo_id, remote_model_path in repos:
            print(f"Trying repo: {repo_id} ({remote_model_path}) ...")
            try:
                downloaded_file = hf_hub_download(
                    repo_id=repo_id,
                    filename=remote_model_path,
                    local_dir=str(target_dir),
                    local_dir_use_symlinks=False
                )
                src_path = Path(downloaded_file)
                if src_path != model_dest:
                    if model_dest.exists():
                        model_dest.unlink()
                    src_path.rename(model_dest)
                print(f"[SUCCESS] Downloaded model to {model_dest}")
                downloaded_model = True
                break
            except Exception as e:
                print(f"[INFO] Repo {repo_id} failed: {e}. Trying fallback...")
        
        if not downloaded_model:
            print("[NOTICE] BGE Reranker model file could not be downloaded right now. Graceful fallback will be used.")

    # Download tokenizer.json and config.json
    aux_files = ["tokenizer.json", "config.json"]
    for aux in aux_files:
        dest = target_dir / aux
        if dest.exists() and dest.stat().st_size > 10:
            print(f"[OK] Already exists: {dest}")
            continue

        print(f"[DOWNLOADING] {aux} ...")
        downloaded_aux = False
        for repo_id, _ in repos:
            try:
                hf_hub_download(
                    repo_id=repo_id,
                    filename=aux,
                    local_dir=str(target_dir),
                    local_dir_use_symlinks=False
                )
                print(f"[SUCCESS] Downloaded {aux} from {repo_id}")
                downloaded_aux = True
                break
            except Exception:
                continue
        if not downloaded_aux:
            print(f"[NOTICE] {aux} could not be downloaded. Will use default config/tokenizer fallback.")


def main():
    print("=" * 60)
    print("LOCUS v3.5 Offline Neural Model Downloader")
    print("Target directory:", MODELS_DIR)
    print("=" * 60)

    download_mdeberta_nli()
    download_bge_reranker()

    print("\n[COMPLETE] Model download check finished.")
    print("LOCUS engine is ready to run offline with zero cloud dependency.")


if __name__ == "__main__":
    main()
