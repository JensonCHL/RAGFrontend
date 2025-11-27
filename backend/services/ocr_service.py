"""
OCR Service Module
Handles PDF OCR processing using Deka AI
"""

import os
import json
import time
import re
from typing import Generator

from core.config import get_ocr_cache_path, OCR_MODEL
from core.clients import deka_client
from core.state import (
    processing_lock, 
    load_processing_states, 
    save_processing_states,
    notify_processing_update
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def page_image_base64(pdf_doc, page_index: int, zoom: float = 3.0) -> str:
    """
    Convert PDF page to base64 image
    
    Args:
        pdf_doc: PyMuPDF document object
        page_index: Page index to convert
        zoom: Zoom factor for image quality
        
    Returns:
        Base64 encoded JPEG image
    """
    import fitz  # PyMuPDF
    from PIL import Image
    import io
    import base64
    
    page = pdf_doc[page_index]
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _clean_text(s: str) -> str:
    """
    Clean extracted text
    
    Args:
        s: Text to clean
        
    Returns:
        Cleaned text
    """
    if not s:
        return ""
    s = s.replace("\x00", " ")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\u200b|\u200c|\u200d|\ufeff", "", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip()


def build_meta_header(meta: dict) -> str:
    """
    Build metadata header for document chunks
    
    Args:
        meta: Metadata dictionary
        
    Returns:
        Formatted metadata header
    """
    company = (meta or {}).get("company", "N/A")
    source = (meta or {}).get("source", "N/A")
    page = (meta or {}).get("page", "N/A")
    return f"Company: {company}\nDocument: {source}\nPage: {page}\n---\n"


# ============================================================================
# OCR PROCESSING
# ============================================================================

def ocr_pdf_pages(
    pdf_path: str, 
    company_id: str, 
    company: str, 
    source_name: str, 
    doc_id: str
) -> Generator[str, None, None]:
    """
    OCR PDF pages and yield progress updates
    
    Args:
        pdf_path: Path to PDF file
        company_id: Company identifier
        company: Company name
        source_name: Source document name
        doc_id: Document ID
        
    Yields:
        JSON progress updates
    """
    # Check cache first
    cache_path = get_ocr_cache_path(company_id, source_name)
    if os.path.exists(cache_path):
        print(f"DEBUG: Found side-by-side OCR cache for {source_name}. Loading from file.")
        try:
            with open(cache_path, 'r') as f:
                cached_pages_data = json.load(f)
            
            yield json.dumps({"status": "started", "message": f"Loading {source_name} from cache..."}) + "\n"
            yield json.dumps({
                "status": "completed",
                "success_pages": len(cached_pages_data),
                "failed_pages": 0,
                "total_pages": len(cached_pages_data),
                "pages_data": cached_pages_data,
                "message": f"OCR completed for {source_name} from cache."
            }) + "\n"
            return
        except Exception as e:
            print(f"ERROR: Failed to load OCR cache for {source_name}: {e}. Re-processing.")

    import fitz  # PyMuPDF
    
    print(f"DEBUG: Starting OCR for {source_name} (doc_id: {doc_id})")
    
    if not deka_client:
        yield json.dumps({"error": "Deka AI client not configured"}) + "\n"
        return
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    success_pages = 0
    failed_pages = 0
    MAX_RETRIES = 3
    
    yield json.dumps({
        "status": "started",
        "message": f"Starting OCR for {source_name} ({total_pages} pages)",
        "total_pages": total_pages,
        "ocrProgress": {
            "current_page": 0,
            "total_pages": total_pages
        }
    }) + "\n"
    
    pages_out = []
    
    for i in range(total_pages):
        # Update processing state
        with processing_lock:
            processing_states = load_processing_states(company_id)
            if doc_id in processing_states:
                processing_states[doc_id].update({
                    "current_page": i + 1,
                    "total_pages": total_pages,
                    "message": f"Processing page {i+1}/{total_pages}"
                })
                if "steps" in processing_states[doc_id] and "ocr" in processing_states[doc_id]["steps"]:
                    processing_states[doc_id]["steps"]["ocr"].update({
                        "current_page": i + 1,
                        "total_pages": total_pages,
                        "message": f"Processing page {i+1}/{total_pages}"
                    })
                save_processing_states(company_id, processing_states)
        
        notify_processing_update({
            "type": "page_started",
            "doc_id": doc_id,
            "page": i + 1,
            "total_pages": total_pages
        })
        
        yield json.dumps({
            "status": "processing",
            "current_page": i + 1,
            "total_pages": total_pages,
            "message": f"Processing page {i+1}/{total_pages}",
            "ocrProgress": {
                "current_page": i + 1,
                "total_pages": total_pages
            }
        }) + "\n"
        
        retries = 0
        page_success = False
        last_error = None
        
        with processing_lock:
            processing_states = load_processing_states(company_id)
            current_file_name = processing_states.get(doc_id, {}).get("current_file") if 'doc_id' in locals() else source_name

        yield json.dumps({
            "status": "page_started",
            "page": i + 1,
            "total_pages": total_pages,
            "currentFile": current_file_name,
            "message": f"Starting OCR for page {i+1}/{total_pages}",
            "ocrProgress": {
                "current_page": i + 1,
                "total_pages": total_pages
            }
        }) + "\n"
        
        while retries < MAX_RETRIES and not page_success:
            try:
                b64_image = page_image_base64(doc, i, zoom=3.0)
                
                yield json.dumps({
                    "status": "page_api_call",
                    "page": i + 1,
                    "total_pages": total_pages,
                    "currentFile": source_name,
                    "message": f"Sending page {i+1}/{total_pages} to OCR service",
                    "ocrProgress": {
                        "current_page": i + 1,
                        "total_pages": total_pages
                    }
                }) + "\n"
                
                try:
                    resp = deka_client.chat.completions.create(
                        model=OCR_MODEL,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are an OCR engine specialized in Indonesian/English legal and technical contracts. "
                                    "Your task is to extract text *exactly as it appears* in the document image, without rewriting or summarizing.\n\n"
                                    "Guidelines:\n"
                                    "- Preserve all line breaks, numbering, and indentation.\n"
                                    "- Keep all headers, footers, and notes if they appear in the image.\n"
                                    "- Preserve tables as text: keep rows and columns aligned with | separators. output it in Markdown table format Pad cells so that columns align visually.\n"
                                    "- Do not translate text — output exactly as in the document.\n"
                                    "- If a cell or field is blank, or contains only dots/dashes (e.g., '.....', '—'), write N/A.\n"
                                    "- Keep units, percentages, currency (e.g., m², kVA, %, Rp.) exactly as written.\n"
                                    "- If text is unclear, output it as ??? instead of guessing."
                                )
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"Extract the text from this page {i+1} of the PDF."},
                                    {"type": "image_url", "image_url": {
                                        "url": f"data:image/jpeg;base64,{b64_image}"}}
                                ]
                            }
                        ],
                        max_tokens=8000,
                        temperature=0,
                        timeout=700
                    )
                    text = (resp.choices[0].message.content or "").strip()
                    text = _clean_text(text)
                    
                    words = len(text.split())
                    
                    page_result = {
                        "page": i + 1,
                        "text": text,
                        "words": words,
                    }
                    pages_out.append(page_result)
                    success_pages += 1
                    page_success = True
                    
                    # Update state with completion
                    with processing_lock:
                        processing_states = load_processing_states(company_id)
                        if doc_id in processing_states:
                            processing_states[doc_id].update({
                                "completed_pages": success_pages,
                                "message": f"Completed page {i+1}/{total_pages}"
                            })
                            if "steps" in processing_states[doc_id] and "ocr" in processing_states[doc_id]["steps"]:
                                processing_states[doc_id]["steps"]["ocr"].update({
                                    "completed_pages": success_pages,
                                    "message": f"Completed page {i+1}/{total_pages}"
                                })
                            save_processing_states(company_id, processing_states)
                    
                    notify_processing_update({
                        "type": "page_completed",
                        "doc_id": doc_id,
                        "page": i + 1,
                        "total_pages": total_pages,
                        "completed_pages": success_pages
                    })
                    
                    yield json.dumps({
                        "status": "page_completed",
                        "page": i + 1,
                        "words": words,
                        "message": f"Completed page {i+1}/{total_pages}",
                        "ocrProgress": {
                            "current_page": i + 1,
                            "total_pages": total_pages
                        }
                    }) + "\n"
                    
                except Exception as e:
                    retries += 1
                    last_error = str(e)
                    if retries < MAX_RETRIES:
                        yield json.dumps({
                            "status": "retry",
                            "page": i + 1,
                            "currentFile": source_name,
                            "retry": retries,
                            "message": f"Retrying page {i+1} (attempt {retries+1}/{MAX_RETRIES})"
                        }) + "\n"
                        time.sleep(2 ** retries)
                    else:
                        raise
                        
            except Exception as e:
                retries += 1
                last_error = str(e)
                if retries < MAX_RETRIES:
                    yield json.dumps({
                        "status": "retry",
                        "page": i + 1,
                        "currentFile": source_name,
                        "retry": retries,
                        "message": f"Retrying page {i+1} (attempt {retries+1}/{MAX_RETRIES})"
                    }) + "\n"
                    time.sleep(2 ** retries)
                else:
                    failed_pages += 1
                    error_msg = f"Failed to process page {i+1} after {MAX_RETRIES} attempts: {last_error}"
                    yield json.dumps({
                        "status": "page_failed",
                        "page": i + 1,
                        "error": error_msg
                    }) + "\n"
                    
                    pages_out.append({
                        "page": i + 1,
                        "text": f"[OCR FAILED: {error_msg}]",
                        "words": 0,
                    })
                    page_success = True
    
    doc.close()

    # Save to cache
    try:
        with open(cache_path, 'w') as f:
            json.dump(pages_out, f, indent=2)
        print(f"DEBUG: Saved OCR results for {source_name} to cache.")
    except Exception as e:
        print(f"ERROR: Failed to save OCR cache for {source_name}: {e}")

    yield json.dumps({
        "status": "completed",
        "success_pages": success_pages,
        "failed_pages": failed_pages,
        "total_pages": total_pages,
        "pages_data": pages_out,
        "message": f"OCR completed for {source_name}: {success_pages}/{total_pages} pages successful"
    }) + "\n"

print("✅ OCR service initialized")
