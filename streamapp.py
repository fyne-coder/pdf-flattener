#!/usr/bin/env python3
"""
streamlit_app.py — Flatten a PDF into an image‑only PDF (low‑memory).

Edit these FOUR constants to resize all text:
  BASE_FONT_PX       – body text & uploader copy
  TITLE_FONT_PX      – main heading
  EXPANDER_FONT_PX   – expander header + slider labels/ticks
  FOOTER_FONT_PX     – footer line
"""

import gc
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable, List

import img2pdf
import streamlit as st
from pdf2image import convert_from_path, pdfinfo_from_path, exceptions as pdf2image_exc

# ── EASY FONT CONTROLS ─────────────────────────────────────
BASE_FONT_PX     = 26
TITLE_FONT_PX    = 48
EXPANDER_FONT_PX = 20
FOOTER_FONT_PX   = 18

# ── Poppler & limits ───────────────────────────────────────
PDFINFO_DIR   = os.path.dirname(shutil.which("pdfinfo") or "")
POPPLER_KW    = {"poppler_path": PDFINFO_DIR} if PDFINFO_DIR else {}
MAX_FILE_SIZE = 25_000_000  # 25 MB
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def rasterise_streaming(
    src: Path,
    dpi: int,
    quality: int,
    out_dir: Path,
    update: Callable[[float], None] | None,
) -> List[Path]:
    try:
        pages = int(pdfinfo_from_path(str(src), **POPPLER_KW)["Pages"])
    except pdf2image_exc.PDFInfoNotInstalledError:
        st.error("Poppler not found. Install poppler-utils and ensure 'pdfinfo' is in PATH.")
        raise

    jpeg_paths: List[Path] = []
    for p in range(1, pages + 1):
        img = convert_from_path(
            str(src), dpi=dpi, first_page=p, last_page=p, **POPPLER_KW
        )[0]
        jpg = out_dir / f"page_{p:04d}.jpg"
        img.save(jpg, "JPEG", quality=quality)
        jpeg_paths.append(jpg)
        del img
        gc.collect()
        if update:
            update(p / pages)
    if update:
        update(1.0)
    return jpeg_paths


def rebuild_pdf(paths: List[Path]) -> bytes:
    pdf = img2pdf.convert([str(p) for p in paths])
    for p in paths:
        p.unlink(missing_ok=True)
    return pdf


def main() -> None:
    st.set_page_config(page_title="PDF Flattener", page_icon="📄", layout="centered")

    # inject CSS variables and global rules
    st.markdown(
        f"""
        <style>
        :root {{
            --font-base: {BASE_FONT_PX}px;
            --font-title: {TITLE_FONT_PX}px;
            --font-expander: {EXPANDER_FONT_PX}px;
            --font-footer: {FOOTER_FONT_PX}px;
        }}
        html, body {{ font-family: 'Inter', sans-serif; }}

        /* all text in main container */
        .block-container * {{
            font-size: var(--font-base) !important;
        }}

        /* headings */
        .block-container h1 {{
            font-size: var(--font-title) !important;
            margin-bottom: .5em;
        }}

        /* file uploader */
        .stFileUploader, .stFileUploader * {{
            font-size: var(--font-base) !important;
        }}

        /* expander header */
        .stExpanderHeader {{
            font-size: var(--font-expander) !important;
            color: inherit !important;
            background-color: transparent !important;
        }}
        /* remove hover/focus outline, box‑shadow & tint */
        .stExpanderHeader:hover,
        .stExpanderHeader:focus,
        .stExpanderHeader:focus-visible {{
            outline: none !important;
            box-shadow: none !important;
            color: inherit !important;
            background-color: transparent !important;
        }}

        /* slider & expander content */
        div[data-testid="stExpander"] *,
        .stSlider label,
        .stSlider span {{
            font-size: var(--font-expander) !important;
        }}

        /* progress bar */
        .stProgress > div > div {{
            height: 16px;
        }}

        /* button */
        button[kind="primary"] {{
            padding: .6rem 1.5rem;
            font-size: 1.1rem;
        }}

        /* hide default footer */
        footer {{ visibility: hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # title and description
    st.markdown(
        "<h1>📄 PDF Flattener</h1>", unsafe_allow_html=True
    )
    st.markdown(
        "<p>Upload a PDF. Each page is rasterised to an image and rebuilt into a <strong>text-free</strong> PDF. "
        "If processing fails, lower DPI or JPEG quality and try again.</p>",
        unsafe_allow_html=True,
    )

    # uploader
    file = st.file_uploader("Choose a PDF", type=["pdf"], label_visibility="visible")

    # options
    with st.expander("Advanced options", expanded=False):
        dpi = st.slider("DPI", 72, 600, 200, step=24)
        quality = st.slider("JPEG quality", 50, 100, 90, step=5)

    # process
    if file:
        if file.size > MAX_FILE_SIZE:
            st.error("File too large. Try a smaller PDF or lower DPI.")
            st.stop()

        if st.button("Flatten PDF", type="primary"):
            logging.info("Flattening %s dpi=%s q=%s", file.name, dpi, quality)
            try:
                with st.spinner("Processing… this may take a moment"):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(file.read())
                        src = Path(tmp.name)
                    with tempfile.TemporaryDirectory() as td:
                        progress = st.progress(0.0)
                        pages = rasterise_streaming(src, dpi, quality, Path(td), progress.progress)
                        flattened = rebuild_pdf(pages)
            except Exception as e:
                logging.exception(e)
                st.error("Processing failed — lower DPI/quality or verify Poppler install.")
                return
            finally:
                src.unlink(missing_ok=True)

            st.success("Done! Download below.")
            st.download_button(
                "⬇️ Download flattened PDF",
                data=flattened,
                file_name=f"{Path(file.name).stem}_flattened.pdf",
                mime="application/pdf",
            )

    # footer
    st.markdown(
        "<div style='text-align:center; font-size: var(--font-footer); margin-top: 3rem;'>"
        "Free to Use – Made by Fyne LLC – Arthur Lee – July 2025"  
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
