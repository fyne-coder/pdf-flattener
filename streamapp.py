#!/usr/bin/env python3
"""
streamlit_app.py — Flatten a PDF into an image‑only PDF (low‑memory, page‑by‑page).

Run:
    streamlit run streamlit_app.py
"""

import os, shutil, sys, logging, gc, tempfile
from pathlib import Path
from typing import Callable, List

import streamlit as st
import img2pdf
from pdf2image import convert_from_path, pdfinfo_from_path, exceptions as pdf2image_exc

# ── Poppler path detection ──────────────────────────────────────────────
_pdfinfo_exe = shutil.which("pdfinfo")
if _pdfinfo_exe:
    POPPLER_PATH = os.path.dirname(_pdfinfo_exe)  # directory, not full exe path
else:
    POPPLER_PATH = os.getenv("POPPLER_PATH")      # optional env override

MAX_FILE_SIZE = 25_000_000  # 25 MB
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# ── helpers ───────────────────────────────────────────────
def rasterise_pdf_streaming(
    src: Path,
    dpi: int,
    quality: int,
    out_dir: Path,
    update: Callable[[float], None] | None = None,
) -> List[Path]:
    """Render one page at a time to keep RAM low."""
    try:
        info_kwargs = {"poppler_path": POPPLER_PATH} if POPPLER_PATH else {}
        page_count = int(pdfinfo_from_path(str(src), **info_kwargs)["Pages"])
    except pdf2image_exc.PDFInfoNotInstalledError:
        st.error(
            "Poppler not found. Install poppler-utils and ensure 'pdfinfo' is on PATH."
        )
        raise

    jpeg_paths: List[Path] = []
    for page_no in range(1, page_count + 1):
        convert_kwargs = {
            "dpi": dpi,
            "first_page": page_no,
            "last_page": page_no,
        }
        if POPPLER_PATH:
            convert_kwargs["poppler_path"] = POPPLER_PATH

        img = convert_from_path(str(src), **convert_kwargs)[0]
        jpg_path = out_dir / f"page_{page_no:04d}.jpg"
        img.save(jpg_path, "JPEG", quality=quality)
        jpeg_paths.append(jpg_path)

        del img
        gc.collect()
        if update:
            update(page_no / page_count)

    if update:
        update(1.0)
    return jpeg_paths


def rebuild_pdf(jpegs: List[Path]) -> bytes:
    """Combine JPEGs into one PDF and delete temp files."""
    pdf_bytes = img2pdf.convert([str(p) for p in jpegs])
    for p in jpegs:
        try:
            os.remove(p)
        except OSError:
            pass
    return pdf_bytes


# ── Streamlit app ────────────────────────────────────────
def main() -> None:
    st.set_page_config(page_title="PDF Flattener", page_icon="📄", layout="centered")
    st.markdown("<style>footer{visibility:hidden;}</style>", unsafe_allow_html=True)

    st.title("📄 PDF Flattener")
    st.write(
        "Upload a PDF. Each page is rasterised to an image and rebuilt into a "
        "**text‑free** PDF. If processing fails, lower DPI or JPEG quality and try again."
    )

    file = st.file_uploader("Choose a PDF", type=["pdf"])
    with st.expander("Options"):
        dpi = st.slider("DPI", 72, 600, 200, step=24)
        quality = st.slider("JPEG quality", 50, 100, 90, step=5)

    if file:
        if file.size > MAX_FILE_SIZE:
            st.error("File too large. Try a smaller PDF or lower DPI.")
            st.stop()

        if st.button("Flatten PDF"):
            logging.info("Flattening %s  dpi=%s  q=%s", file.name, dpi, quality)
            try:
                with st.spinner("Processing…"):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(file.read())
                        src_path = Path(tmp.name)

                    with tempfile.TemporaryDirectory() as td:
                        progress = st.progress(0.0)
                        jpeg_paths = rasterise_pdf_streaming(
                            src_path, dpi, quality, Path(td), update=progress.progress
                        )
                        flattened = rebuild_pdf(jpeg_paths)

            except Exception as err:
                logging.exception(err)
                st.error(
                    "Processing failed—possibly out of memory or Poppler missing. "
                    "Lower DPI/quality or verify Poppler install and try again."
                )
                return
            finally:
                try:
                    os.remove(src_path)
                except OSError:
                    pass

            st.success("Done! Download below.")
            st.download_button(
                "Download flattened PDF",
                data=flattened,
                file_name=f"{Path(file.name).stem}_flattened.pdf",
                mime="application/pdf",
            )

    st.markdown(
        "<div style='text-align:center;margin-top:3rem;font-size:0.9rem;'>"
        "Free to Use – Made by Fyne LLC – Arthur Lee – July 2025"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
