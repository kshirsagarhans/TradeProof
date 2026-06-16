"""
Gemini API extraction pipeline.
Uses text + optional vision for scanned PDFs.
"""
import json
import re
import google.generativeai as genai
from config import GEMINI_API_KEY, DEFAULT_MODEL, FALLBACK_MODEL, MAX_RETRIES
from utils.pdf_reader import extract_text_from_pdf, pdf_to_images_base64
import streamlit as st

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

BL_EXTRACTION_PROMPT = """
You are an expert trade document parser specializing in Ocean Bills of Lading (BL).
Extract ALL data from the document text provided below.

Return ONLY a valid JSON object. No markdown formatting, no code blocks, no explanation.
Use null for any field not found in the document.

Required JSON schema:
{
  "bl_number": "string — Ocean Bill of Lading reference number",
  "exporter_name": "string — full name of shipper/exporter",
  "exporter_address": "string — complete address on one line",
  "consignee_name": "string — full consignee name",
  "consignee_address": "string — complete consignee address",
  "port_of_loading": "string — port where goods are loaded",
  "port_of_discharge": "string — port where goods are discharged",
  "port_of_final_destination": "string — final destination port/place",
  "shipping_bill_references": [
    {"sb_number": "string", "sb_date": "string in DD/MM/YYYY format"}
  ],
  "total_packages": number or null,
  "gross_weight": number or null,
  "gross_weight_unit": "KG or MT or LB",
  "containers": [
    {"container_number": "string", "seal_number": "string"}
  ],
  "hs_code": "string or null",
  "hs_description": "string or null",
  "invoice_number": "string or null",
  "invoice_amount": number or null,
  "invoice_currency": "USD or INR or EUR or null"
}

Normalization rules:
- Normalize all string values to UPPERCASE
- Strip all leading/trailing whitespace
- Combine multi-line addresses into single strings separated by commas
- For containers: extract ALL container/seal number pairs found anywhere in the document
- For gross_weight: extract numeric value only, put unit in gross_weight_unit
- If multiple SB references appear, list all of them in shipping_bill_references array
"""

SB_EXTRACTION_PROMPT = """
You are an expert trade document parser specializing in Indian Customs Shipping Bills (SB).
Extract ALL data from the Shipping Bill document text provided below.

Return ONLY a valid JSON object. No markdown formatting, no code blocks, no explanation.
Use null for any field not found.

Required JSON schema:
{
  "sb_number": "string — Shipping Bill number",
  "sb_date": "string — date in DD/MM/YYYY format",
  "exporter_name": "string",
  "exporter_address": "string — complete address on one line",
  "consignee_name": "string",
  "consignee_address": "string",
  "port_of_loading": "string",
  "port_of_discharge": "string",
  "port_of_final_destination": "string",
  "pkg_total": number or null,
  "gross_weight_total": number or null,
  "gross_weight_unit": "KG or MT or LB",
  "containers": [
    {"container_number": "string", "seal_number": "string"}
  ],
  "hs_code": "string or null",
  "hs_description": "string or null",
  "invoice_number": "string or null",
  "invoice_amount": number or null,
  "invoice_currency": "string or null"
}

Normalization rules:
- All strings in UPPERCASE
- Dates in DD/MM/YYYY format
- Addresses combined to single line
- Extract ALL container/seal pairs
- pkg_total = total number of packages/cartons in this document
"""

def _clean_json_response(text: str) -> str:
    """Strip markdown code fences and whitespace from Gemini response."""
    text = text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    return text.strip()

@st.cache_data(show_spinner=False)
def extract_bl_data(pdf_bytes: bytes, api_key: str = None) -> dict:
    """Extract Bill of Lading data using Gemini API."""
    key = api_key or GEMINI_API_KEY
    if key:
        genai.configure(api_key=key)

    raw_text = extract_text_from_pdf(pdf_bytes, "Bill of Lading")
    is_low_text = "[LOW_TEXT_WARNING]" in raw_text

    model = genai.GenerativeModel(DEFAULT_MODEL)

    for attempt in range(MAX_RETRIES):
        try:
            if is_low_text:
                # Vision fallback for scanned PDFs
                images = pdf_to_images_base64(pdf_bytes)
                contents = [
                    BL_EXTRACTION_PROMPT,
                    "Here is the Bill of Lading document (image-based):"
                ]
                for img_b64 in images[:4]:  # Max 4 pages
                    contents.append({
                        "inline_data": {"mime_type": "image/png", "data": img_b64}
                    })
            else:
                contents = f"{BL_EXTRACTION_PROMPT}\n\nDOCUMENT TEXT:\n{raw_text}"

            response = model.generate_content(
                contents,
                generation_config={"temperature": 0.1, "max_output_tokens": 4096}
            )
            cleaned = _clean_json_response(response.text)
            data = json.loads(cleaned)
            data["raw_text"] = raw_text[:2000]  # Store first 2000 chars
            return {"success": True, "data": data, "raw_text": raw_text}

        except json.JSONDecodeError as e:
            if attempt == MAX_RETRIES - 1:
                return {"success": False, "error": f"JSON parse failed: {str(e)}", "raw_text": raw_text}
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return {"success": False, "error": str(e), "raw_text": raw_text}

    return {"success": False, "error": "Max retries exceeded", "raw_text": raw_text}


@st.cache_data(show_spinner=False)
def extract_sb_data(pdf_bytes: bytes, filename: str = "SB", api_key: str = None) -> dict:
    """Extract Shipping Bill data using Gemini API."""
    key = api_key or GEMINI_API_KEY
    if key:
        genai.configure(api_key=key)

    raw_text = extract_text_from_pdf(pdf_bytes, filename)
    is_low_text = "[LOW_TEXT_WARNING]" in raw_text

    model = genai.GenerativeModel(DEFAULT_MODEL)

    for attempt in range(MAX_RETRIES):
        try:
            if is_low_text:
                images = pdf_to_images_base64(pdf_bytes)
                contents = [SB_EXTRACTION_PROMPT]
                for img_b64 in images[:4]:
                    contents.append({
                        "inline_data": {"mime_type": "image/png", "data": img_b64}
                    })
            else:
                contents = f"{SB_EXTRACTION_PROMPT}\n\nDOCUMENT TEXT:\n{raw_text}"

            response = model.generate_content(
                contents,
                generation_config={"temperature": 0.1, "max_output_tokens": 4096}
            )
            cleaned = _clean_json_response(response.text)
            data = json.loads(cleaned)
            data["raw_text"] = raw_text[:2000]
            data["source_filename"] = filename
            return {"success": True, "data": data, "raw_text": raw_text}

        except json.JSONDecodeError as e:
            if attempt == MAX_RETRIES - 1:
                return {"success": False, "error": f"JSON parse failed: {str(e)}", "raw_text": raw_text, "source_filename": filename}
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return {"success": False, "error": str(e), "raw_text": raw_text, "source_filename": filename}

    return {"success": False, "error": "Max retries exceeded"}
