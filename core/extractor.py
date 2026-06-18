"""
AI API extraction pipeline.
Supports both Google Gemini and Azure OpenAI via a unified router interface.
"""
import json
import re
import google.generativeai as genai
from openai import AzureOpenAI
from config import MAX_RETRIES, DEFAULT_MODEL
from utils.pdf_reader import extract_text_from_pdf, pdf_to_images_base64

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
    if not text:
        return "{}"
    text = text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    return text.strip()

def _extract_with_gemini(raw_text: str, images: list[str], prompt: str, is_low_text: bool, credentials: dict) -> tuple[bool, str, str]:
    """Internal handler for Google Gemini extraction."""
    api_key = credentials.get("api_key")
    if not api_key:
        return False, "Gemini API key is missing.", "{}"
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(DEFAULT_MODEL)
    
    for attempt in range(MAX_RETRIES):
        try:
            if is_low_text and images:
                contents = [prompt, "Here is the document (image-based):"]
                for img_b64 in images[:4]:
                    contents.append({
                        "inline_data": {"mime_type": "image/png", "data": img_b64}
                    })
            else:
                contents = f"{prompt}\n\nDOCUMENT TEXT:\n{raw_text}"

            response = model.generate_content(
                contents,
                generation_config={"temperature": 0.1, "max_output_tokens": 4096}
            )
            cleaned = _clean_json_response(response.text)
            return True, "", cleaned
            
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return False, f"Gemini Error: {str(e)}", "{}"

    return False, "Max retries exceeded", "{}"


def _extract_with_azure(raw_text: str, images: list[str], prompt: str, is_low_text: bool, credentials: dict) -> tuple[bool, str, str]:
    """Internal handler for Azure OpenAI extraction."""
    api_key = credentials.get("api_key")
    endpoint = credentials.get("endpoint")
    api_version = credentials.get("api_version")
    deployment_name = credentials.get("deployment_name")
    
    if not all([api_key, endpoint, api_version, deployment_name]):
        return False, "Missing Azure OpenAI credentials.", "{}"

    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version
    )
    
    for attempt in range(MAX_RETRIES):
        try:
            messages = [{"role": "system", "content": prompt}]
            
            if is_low_text and images:
                user_content = [{"type": "text", "text": "Here is the document. Extract the required data."}]
                for img_b64 in images[:4]:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                    })
                messages.append({"role": "user", "content": user_content})
            else:
                messages.append({"role": "user", "content": f"DOCUMENT TEXT:\n{raw_text}"})

            response = client.chat.completions.create(
                model=deployment_name,
                messages=messages,
                temperature=0.1,
                max_tokens=4096,
                response_format={"type": "json_object"}
            )
            cleaned = _clean_json_response(response.choices[0].message.content)
            return True, "", cleaned
            
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return False, f"Azure OpenAI Error: {str(e)}", "{}"

    return False, "Max retries exceeded", "{}"


def extract_bl_data(pdf_bytes: bytes, ai_config: dict) -> dict:
    """Router function to extract Bill of Lading data."""
    provider = ai_config.get("provider", "gemini").lower()
    
    if provider == "mock":
        import time
        time.sleep(1) # Simulate API latency
        mock_data = {
            "bl_number": "MOCK-BL-12345",
            "exporter_name": "ACME GLOBAL EXPORTS",
            "exporter_address": "123 INDUSTRIAL WAY, FAKEVILLE",
            "consignee_name": "GLOBEX IMPORT INC",
            "consignee_address": "456 IMPORT ROAD, MOCK CITY",
            "port_of_loading": "SHANGHAI",
            "port_of_discharge": "LOS ANGELES",
            "port_of_final_destination": "LOS ANGELES",
            "shipping_bill_references": [{"sb_number": "SB-999", "sb_date": "01/01/2026"}],
            "total_packages": 100,
            "gross_weight": 5000,
            "gross_weight_unit": "KG",
            "containers": [{"container_number": "CONT1234567", "seal_number": "SEAL888"}],
            "hs_code": "8471.30",
            "hs_description": "LAPTOP COMPUTERS",
            "invoice_number": "INV-2026-001",
            "invoice_amount": 50000,
            "invoice_currency": "USD"
        }
        return {"success": True, "data": mock_data, "raw_text": "MOCK PDF CONTENT - BYPASSED API"}

    raw_text = extract_text_from_pdf(pdf_bytes, "Bill of Lading")
    is_low_text = "[LOW_TEXT_WARNING]" in raw_text
    images = pdf_to_images_base64(pdf_bytes) if is_low_text else []

    credentials = ai_config.get("credentials", {})
    
    if provider == "azure":
        success, error, json_str = _extract_with_azure(raw_text, images, BL_EXTRACTION_PROMPT, is_low_text, credentials)
    else:
        success, error, json_str = _extract_with_gemini(raw_text, images, BL_EXTRACTION_PROMPT, is_low_text, credentials)

    if not success:
        return {"success": False, "error": error, "raw_text": raw_text}

    try:
        data = json.loads(json_str)
        data["raw_text"] = raw_text[:2000]
        return {"success": True, "data": data, "raw_text": raw_text}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse failed: {str(e)}", "raw_text": raw_text}


def extract_sb_data(pdf_bytes: bytes, filename: str, ai_config: dict) -> dict:
    """Router function to extract Shipping Bill data."""
    provider = ai_config.get("provider", "gemini").lower()
    
    if provider == "mock":
        import time
        time.sleep(1) # Simulate API latency
        mock_data = {
            "sb_number": "SB-999",
            "sb_date": "01/01/2026",
            "exporter_name": "ACME GLOBAL EXPORTS",
            "exporter_address": "123 INDUSTRIAL WAY, FAKEVILLE",
            "consignee_name": "GLOBEX IMPORT INC",
            "consignee_address": "456 IMPORT ROAD, MOCK CITY",
            "port_of_loading": "SHANGHAI",
            "port_of_discharge": "LOS ANGELES",
            "port_of_final_destination": "LOS ANGELES",
            "pkg_total": 100,
            "gross_weight_total": 5000,
            "gross_weight_unit": "KG",
            "containers": [{"container_number": "CONT1234567", "seal_number": "SEAL888"}],
            "hs_code": "8471.30",
            "hs_description": "LAPTOP COMPUTERS",
            "invoice_number": "INV-2026-001",
            "invoice_amount": 50000,
            "invoice_currency": "USD"
        }
        return {"success": True, "data": mock_data, "raw_text": "MOCK PDF CONTENT - BYPASSED API", "source_filename": filename}

    raw_text = extract_text_from_pdf(pdf_bytes, filename)
    is_low_text = "[LOW_TEXT_WARNING]" in raw_text
    images = pdf_to_images_base64(pdf_bytes) if is_low_text else []

    credentials = ai_config.get("credentials", {})
    
    if provider == "azure":
        success, error, json_str = _extract_with_azure(raw_text, images, SB_EXTRACTION_PROMPT, is_low_text, credentials)
    else:
        success, error, json_str = _extract_with_gemini(raw_text, images, SB_EXTRACTION_PROMPT, is_low_text, credentials)

    if not success:
        return {"success": False, "error": error, "raw_text": raw_text, "source_filename": filename}

    try:
        data = json.loads(json_str)
        data["raw_text"] = raw_text[:2000]
        data["source_filename"] = filename
        return {"success": True, "data": data, "raw_text": raw_text}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse failed: {str(e)}", "raw_text": raw_text, "source_filename": filename}

SEAL_EXTRACTION_PROMPT = """
You are a shipping container verification expert.
Analyze the provided photos of physical container seals and doors.
Extract any container numbers and seal numbers clearly visible.

Return ONLY a valid JSON object. No markdown formatting, no code blocks.

Required JSON schema:
{
  "containers": [
    {"container_number": "string or null", "seal_number": "string or null"}
  ]
}
"""

def extract_seal_data(image_bytes_list: list[bytes], ai_config: dict) -> dict:
    """Router function to extract seal data from physical images."""
    provider = ai_config.get("provider", "gemini").lower()
    
    if provider == "mock":
        import time
        time.sleep(1) # Simulate API latency
        mock_data = {
            "containers": [{"container_number": "CONT1234567", "seal_number": "SEAL888"}]
        }
        return {"success": True, "data": mock_data}

    import base64
    images = [base64.b64encode(img).decode('utf-8') for img in image_bytes_list]
    
    credentials = ai_config.get("credentials", {})
    
    # We must treat this as "low text" because it's purely image-based
    is_low_text = True 
    
    if provider == "azure":
        success, error, json_str = _extract_with_azure("", images, SEAL_EXTRACTION_PROMPT, is_low_text, credentials)
    else:
        success, error, json_str = _extract_with_gemini("", images, SEAL_EXTRACTION_PROMPT, is_low_text, credentials)

    if not success:
        return {"success": False, "error": error}

    try:
        data = json.loads(json_str)
        return {"success": True, "data": data}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse failed: {str(e)}"}

