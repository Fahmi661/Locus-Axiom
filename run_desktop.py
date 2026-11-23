"""
LOCUS Desktop Application Runner.
Enforces 100% Offline execution and launches desktop wrapper / browser interface.
"""

import os
import sys

# Force 100% Offline mode for Hugging Face and ML libraries
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import desktop_launcher

if __name__ == "__main__":
    desktop_launcher.main()
