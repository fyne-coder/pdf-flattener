#!/usr/bin/env python3
"""
streamlit_app.py – Flatten a PDF into a picture‑only PDF (in memory).

Const controls: BASE_FONT_PX, TITLE_FONT_PX, EXPANDER_FONT_PX, FOOTER_FONT_PX
"""

import io, gc, logging, os, shutil, sys
from pathlib import Path
from typing import List, Callable, Optional

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
MAX_FILE_SIZE = 25_000_000  # 25 MB

logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def flatten_pdf_in_memory(
    pdf_bytes: bytes,
    dpi: int,
    quality: int,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> bytes:
    """Render PDF pages in memory and return flattened PDF bytes."""
    try:
        info = pdfinfo_from_bytes(pdf_bytes, **POPPLER_KW)
        page_count = int(info.get("Pages", 0))
    except pdf2image_exc.PDFInfoNotInstalledError:
        st.error(
            "Poppler not found. Install poppler‑utils and be sure 'pdfinfo' is in PATH."
        )
        raise

    buffers: List[io.BytesIO] = []
    for page_no in range(1, page_count + 1):
        imgs = convert_from_bytes(
            pdf_bytes,
            dpi=dpi,
            first_page=page_no,
            last_page=page_no,
            **POPPLER_KW,
        )
        img = imgs[0]
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=quality)
        buf.seek(0)
        buffers.append(buf)
        del img, imgs
        gc.collect()

        # update progress if callback supplied
        if progress_cb:
            progress_cb(page_no / page_count)

    return img2pdf.convert(buffers)


def main():
    st.set_page_config(page_title="PDF Flattener", page_icon="📄", layout="centered")

    # Inject global CSS
    st.markdown(
        f"""
        <style>
        :root {{
            --font-base:{BASE_FONT_PX}px;
            --font-title:{TITLE_FONT_PX}px;
            --font-expander:{EXPANDER_FONT_PX}px;
            --font-footer:{FOOTER_FONT_PX}px;
        }}
        html,body{{font-family:'Inter',sans-serif;}}
        .block-container *{{font-size:var(--font-base)!important;}}
        .block-container h1{{font-size:var(--font-title)!important;margin-bottom:.5em;}}
        .stFileUploader *{{font-size:var(--font-base)!important;}}

        div[data-testid="stExpander"]>div[role="button"]{{
            font-size:var(--font-expander)!important;
            background:transparent!important;
        }}
        div[data-testid="stExpander"] *, .stSlider label{{
            font-size:var(--font-expander)!important;
        }}
        /* numeric values – smaller and lifted higher */
        .stSlider span {{
        font-size:calc(var(--font-expander)*0.8)!important;
        position:relative; top:-14px;
        }}
        /* numeric value on slider thumb */
        .stSlider [class*="ThumbValue"]{{
        font-size:calc(var(--font-expander)*0.8) !important;
        transform:translateY(-12px) !important;  /* lift off the track */
        }}
        .stProgress>div>div{{height:16px;}}
        button[kind="primary"]{{padding:.6rem 1.5rem;font-size:1.1rem;}}
        footer{{visibility:hidden;}}
        </style>
        """,
        unsafe_allow_html=True,
    )



    # Title
    st.markdown("<h1>📄 PDF Flattener</h1>", unsafe_allow_html=True)

    # Friendly instructions
    st.info(
        """
        • **Upload** the PDF you marked or signed.  
        • We flatten every page into a picture‑only PDF.  
        • Redactions, pen strokes, and signatures stay locked in place, so no one can copy, search, or uncover the covered text.
        """
    )
    st.markdown(
        "<p>If it errors, lower the DPI or image quality and try again.</p>",
        unsafe_allow_html=True,
    )

    # ── FORM START ──────────────────────────────────────────
    with st.form("flattener_form", clear_on_submit=True):
        uploaded = st.file_uploader("Choose a PDF", type=["pdf"])
        with st.expander("Advanced options", expanded=False):
            dpi = st.slider("DPI", 72, 600, 200, step=24)
            quality = st.slider("JPEG quality", 50, 100, 90, step=5)
        submit = st.form_submit_button("Flatten PDF", use_container_width=True)

    # ── AFTER SUBMIT ────────────────────────────────────────
    if submit:
        if not uploaded:
            st.error("Please upload a PDF first.")
        elif uploaded.size > MAX_FILE_SIZE:
            st.error("File too large. Try a smaller PDF or lower DPI.")
        else:
            logging.info("Flattening %s dpi=%s q=%s", uploaded.name, dpi, quality)

            # set up progress bar
            progress = st.progress(0.0, text="Rasterising pages…")

            try:
                pdf_bytes = uploaded.read()
                flattened = flatten_pdf_in_memory(
                    pdf_bytes,
                    dpi,
                    quality,
                    progress_cb=lambda f: progress.progress(f),
                )
                progress.empty()  # clear progress bar

                st.success("Done! Download below.")
                st.download_button(
                    "⬇️ Download flattened PDF",
                    data=flattened,
                    file_name=f"{Path(uploaded.name).stem}_flattened.pdf",
                    mime="application/pdf",
                )
            except Exception:
                progress.empty()
                st.error("Flattening failed – lower DPI or check Poppler install.")

    # Footer
    st.markdown(
        "<div style='text-align:center;font-size:var(--font-footer);margin-top:3rem;'>"
        "Free to use – Made by Fyne LLC – Arthur Lee – July 2025"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
