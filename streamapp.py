#!/usr/bin/env python3
"""
streamlit_main.py —  Flatten a PDF into an image‑only PDF.

Run locally:
    streamlit run streamlit_main.py

Requires:
    streamlit, pdf2image, pillow (<11), img2pdf
    Poppler utilities ('pdfinfo', 'pdftoppm') on PATH.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable, List

import img2pdf
import streamlit as st
from pdf2image import convert_from_path, exceptions as pdf2image_exc


# ── helpers ──────────────────────────────────────────────────────────────
def rasterise_pdf(
    src: Path,
    dpi: int,
    quality: int,
    out_dir: Path,
    update: Callable[[float], None] | None = None,
) -> List[Path]:
    """Render each page to JPEG and return their paths."""
    try:
        pages = convert_from_path(str(src), dpi=dpi)
    except pdf2image_exc.PDFInfoNotInstalledError:
        st.error("Poppler not found. Install it and add 'pdfinfo' to PATH.")
        raise
    except Exception as err:
        st.error(f"Unable to open PDF: {err}")
        raise

    total = len(pages)
    paths: List[Path] = []
    for idx, page in enumerate(pages, 1):
        if update:
            update(idx / total)
        jpg = out_dir / f"page_{idx:04d}.jpg"
        page.convert("RGB").save(jpg, "JPEG", quality=quality)
        paths.append(jpg)

    if update:
        update(1.0)
    return paths


def rebuild_pdf(jpegs: List[Path]) -> bytes:
    """Combine JPEG pages into one PDF and return bytes."""
    return img2pdf.convert([str(p) for p in jpegs])


# ── main app ─────────────────────────────────────────────────────────────
def main() -> None:
    st.set_page_config(
        page_title="PDF Flattener",
        page_icon="📄",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    # hide default Streamlit footer for a cleaner Community Cloud look
    st.markdown(
        """
        <style>
            footer {visibility: hidden;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("📄 PDF Flattener")
    st.markdown(
        "Upload a PDF. Each page is rasterised to an image, then rebuilt into a "
        "**text‑free** PDF."
    )

    file = st.file_uploader("Choose a PDF", type=["pdf"])
    with st.expander("Options"):
        dpi = st.slider("DPI", 72, 600, 300, step=24)
        quality = st.slider("JPEG quality", 50, 100, 95, step=5)

    if file and st.button("Flatten PDF"):
        with st.spinner("Processing…"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                tmp_pdf.write(file.read())
                src_path = Path(tmp_pdf.name)

            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    progress = st.progress(0.0)
                    jpeg_paths = rasterise_pdf(
                        src_path, dpi, quality, Path(tmpdir), update=progress.progress
                    )
                    flattened = rebuild_pdf(jpeg_paths)
            finally:
                os.remove(src_path)

        st.success("Done! Download below.")
        st.download_button(
            "Download flattened PDF",
            data=flattened,
            file_name=f"{Path(file.name).stem}_flattened.pdf",
            mime="application/pdf",
        )

    # centered footer
    st.markdown(
        """
        <div style="text-align:center; margin-top:3rem; font-size:0.9rem;">
            Free to Use - Made by Fyne LLC - Arthur Lee - July 2025
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
