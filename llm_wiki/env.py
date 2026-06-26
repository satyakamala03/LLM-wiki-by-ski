"""Process env for sentence-transformers / transformers (Keras 3 compat).

Import this module before any Hugging Face stack import, or call ``apply_tf_compat()``.
"""

from __future__ import annotations


class _TorchClassesPathShim(list):
    """Fake ``__path__`` for ``torch.classes`` so Streamlit's watcher does not probe C++ classes."""

    _path: list[str] = []


def apply_tf_compat() -> None:
    import os

    # Disable TensorFlow backend in transformers (avoids Keras 3 / tf-keras requirement).
    os.environ["USE_TF"] = "0"
    os.environ["TRANSFORMERS_NO_TF"] = "1"
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def apply_streamlit_compat() -> None:
    """Streamlit server options that must be set before ``import streamlit``."""
    import os

    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")


def patch_torch_for_streamlit_watcher() -> None:
    """Stop Streamlit's file watcher from probing ``torch.classes`` (log noise only)."""
    import sys

    try:
        import torch
    except ImportError:
        return

    shim: _TorchClassesPathShim = _TorchClassesPathShim()
    for target in (torch.classes, sys.modules.get("torch.classes")):
        if target is None:
            continue
        try:
            target.__path__ = shim  # type: ignore[attr-defined]
        except Exception:
            pass


apply_tf_compat()
apply_streamlit_compat()
