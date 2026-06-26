#!/usr/bin/env python3
"""Streamlit UI for LLM Wiki — run: streamlit run app.py"""

from __future__ import annotations

import llm_wiki.env  # noqa: F401 — TF + Streamlit compat before other imports

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / "llm_wiki" / "config" / ".env")

from llm_wiki.env import apply_streamlit_compat, apply_tf_compat, patch_torch_for_streamlit_watcher

apply_streamlit_compat()
apply_tf_compat()

try:
    import torch  # noqa: F401 — load early so torch.classes can be patched before chat

    patch_torch_for_streamlit_watcher()
except ImportError:
    pass

from llm_wiki.ui.main import render_app

render_app()
