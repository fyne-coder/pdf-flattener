#!/usr/bin/env python3
"""
streamlit_app.py — Flatten a PDF into an image‑only PDF (low‑memory, no disk files).

Edit these FOUR constants to resize all text:
  BASE_FONT_PX       – body text & uploader copy
  TITLE_FONT_PX      – main heading
  EXPANDER_FONT_PX   – expander header + slider labels/ticks
  FOOTER_FONT_PX     – footer line
"""

import io
import gc
import logging
import os
import shutil
import sys
from typing import Callable, List

import img2pdf
import streamlit as st
from pdf2image import (
    convert_from_bytes,
    pdfinfo_from_bytes,
    exceptions as pdf2image_exc,
)

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


def flatten_pdf_in_memory(pdf_bytes: bytes, dpi: int, quality: int) -> bytes:
    """Render PDF pages in memory and return flattened PDF bytes."""
    try:
        info = pdfinfo_from_bytes(pdf_bytes, **POPPLER_KW)
        page_count = int(info.get("Pages", 0))
    except pdf2image_exc.PDFInfoNotInstalledError:
        st.error("Poppler not found. Install poppler‑utils and ensure 'pdfinfo' is in PATH.")
        raise

    buffers: List[io.BytesIO] = []
    for page_no in range(1, page_count + 1):
        imgs = convert_from_bytes(
            pdf_bytes, dpi=dpi, first_page=page_no, last_page=page_no, **POPPLER_KW
        )
        img = imgs[0]
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=quality)
        buf.seek(0)
        buffers.append(buf)
        del img, imgs
        gc.collect()

    # combine into PDF
    pdf_bytes_out = img2pdf.convert(buffers)
    return pdf_bytes_out


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

          /* expander header: clickable element */
          div[data-testid="stExpander"] > div[role="button"] {{
            font-size: var(--font-expander) !important;
            background-color: transparent !important;
            color: inherit !important;
            outline: none !important;
            box-shadow: none !important;
          }}
          /* remove hover/focus effects */
          div[data-testid="stExpander"] > div[role="button"]:hover,
          div[data-testid="stExpander"] > div[role="button"]:focus,
          div[data-testid="stExpander"] > div[role="button"]:focus-visible {{
            background-color: transparent !important;
          }}
          /* ensure children inherit color */
          div[data-testid="stExpander"] > div[role="button"] * {{
            color: inherit !important;
          }}

          /* slider & expander content */
          div[data-testid="stExpander"] *,
          .stSlider label,
          .stSlider span {{
            font-size: var(--font-expander) !important;
          }}

          /* progress bar */
          .stProgress > div > div {{ height: 16px; }}

          /* button */
          button[kind="primary"] {{ padding: .6rem 1.5rem; font-size: 1.1rem; }}

          /* hide default footer */
          footer {{ visibility: hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # title and description
    st.markdown(
        f"<h1 style='font-size: var(--font-title);'>📄 PDF Flattener</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='font-size: var(--font-base); line-height:1.6;'>"
        "Upload a PDF. Each page is rasterised in memory to an image and rebuilt into a <strong>text-free</strong> PDF. "
        "If processing fails, lower DPI or JPEG quality and try again."
        "</p>",
        unsafe_allow_html=True,
    )

    # uploader
    file = st.file_uploader(
        "Choose a PDF", type=["pdf"], label_visibility="visible"
    )

    # options expander
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
                pdf_bytes = file.read()
                with st.spinner("Processing… this may take a moment"):
                    flattened = flatten_pdf_in_memory(pdf_bytes, dpi, quality)
            except Exception as e:
                logging.exception(e)
                st.error("Processing failed — lower DPI/quality or verify Poppler install.")
                return

            st.success("Done! Download below.")
            st.download_button(
                "⬇️ Download flattened PDF",
                data=flattened,
                file_name=f"{Path(file.name).stem}_flattened.pdf",
                mime="application/pdf",
            )

    # footer
    st.markdown(
        f"<div style='text-align:center; font-size: var(--font-footer); margin-top:3rem;'>"  
        "Free to Use – Made by Fyne LLC – Arthur Lee – July 2025"  
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
