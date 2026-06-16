"""
PDF text extraction using PyMuPDF.
Extracts text page-by-page and concatenates.
Falls back to image-based OCR prompt if text is sparse.
"""
import fitz  # PyMuPDF
import io

def extract_text_from_pdf(pdf_bytes: bytes, filename: str = "document") -> str:
    """Extract all text from a PDF file given as bytes."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = []
        for page_num, page in enumerate(doc, 1):
            text = page.get_text("text")
            full_text.append(f"--- PAGE {page_num} ---\n{text}")
        doc.close()
        combined = "\n".join(full_text).strip()
        if len(combined) < 100:
            return f"[LOW_TEXT_WARNING] Extracted only {len(combined)} chars from {filename}. Document may be scanned/image-based."
        return combined
    except Exception as e:
        return f"[EXTRACTION_ERROR] Failed to extract text from {filename}: {str(e)}"

def pdf_to_images_base64(pdf_bytes: bytes) -> list[str]:
    """Convert PDF pages to base64 images for vision-based extraction."""
    import base64
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        images.append(base64.b64encode(img_bytes).decode("utf-8"))
    doc.close()
    return images
