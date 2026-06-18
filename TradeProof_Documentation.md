# TradeProof — Intelligent Trade Document Reconciliation Platform
## Project Documentation & Usage Guide

---

### 1. Large Language Models (LLMs) Used
TradeProof leverages cutting-edge multimodal large language models to accurately extract structured data from complex trade documents and physical photos. The user can toggle between two primary providers:

*   **Google Gemini (Primary):** Utilizes Google's `gemini-2.5-pro` (or `gemini-1.5-pro`) for high-speed, highly accurate multimodal extraction of PDFs (Bill of Lading, Shipping Bills) and image processing for physical seals.
*   **Azure OpenAI (Enterprise Alternative):** Utilizes OpenAI models hosted securely on Microsoft Azure (typically `gpt-4o` or `gpt-4-turbo`), ensuring enterprise-grade data privacy, strict JSON schema adherence, and rigorous token limits.

### 2. APIs & Core Technologies
*   **Generative AI APIs:** 
    *   `google.generativeai` SDK for Gemini integration.
    *   `openai` Python SDK configured for Azure endpoints.
*   **Frontend Framework:** Streamlit (v1.30+) for the interactive, glassmorphism-styled web interface.
*   **Data Processing:** `pandas` for handling table structures and exporting data.
*   **Geospatial Visualization:** `pydeck` (PyDeck) integrated with Mapbox to render the dynamic cargo route arcs based on extracted geographic coordinates.
*   **Database:** Local `sqlite3` for persistent storage of historical audits and human override justifications.
*   **File Parsing:** `PyMuPDF` (`fitz`) and `Pillow` (`PIL`) for handling PDF byte streams and image rendering before sending them to the Vision APIs.

---

### 3. Key Feature List
1.  **AI Data Extraction Engine:** Automatically extracts complex fields (Identifiers, HS Codes, Weights, Container/Seal Numbers) from unstructured Master Bills of Lading and Supporting Shipping Bills.
2.  **7-Point Reconciliation Engine:** Cross-references the extracted data across seven critical categories to instantly spot customs discrepancies.
3.  **Physical-to-Digital Verification (Multi-Modal AI):** Users can upload photos of physical container seals. The AI extracts the stamped container and seal numbers and verifies them against the digital documents, flagging high-severity "TAMPER WARNINGS".
4.  **Human-in-the-Loop Overrides:** Users can review discrepancies, provide a written justification (e.g., "Known typo approved by customs"), and officially override the warning. This action instantly updates the metrics and is permanently logged in the database.
5.  **Interactive Analytics Dashboard:** Real-time generation of pie charts and metric cards detailing documentation integrity and clearance hold statuses.
6.  **Cargo Route Visualization:** Automatically extracts Port of Loading and Port of Discharge coordinates to draw a 3D animated route map of the vessel's journey.
7.  **Historical Audit Tracking:** Every generated report, including the human overrides, is saved securely in a local database and can be retrieved at any time from the "Past Audits" tab.
8.  **Multi-Format Exporting:** Instantly download finalized audit reports in **Excel (`.xlsx`)**, **JSON**, or **HTML** formats for external compliance record-keeping.

---

### 4. Step-by-Step Guide to Using TradeProof

**Step 1: Configure AI Provider**
1. Open the application in your browser.
2. In the left-hand sidebar, select your preferred **AI Provider** (Google Gemini or Azure OpenAI).
3. Enter the required API Keys and Endpoints for your chosen provider. *(Note: These are processed securely in memory and are required to run the AI engine).*

**Step 2: Upload Documents**
1. Navigate to the **"New Audit"** tab.
2. Under "Document Upload Pipeline", drag and drop your **Master Bill of Lading** (PDF) into the first box.
3. Drag and drop all associated **Shipping Bills** (PDFs) into the second box. You can upload multiple files here.
4. *(Optional)* If you have photos of the physical container seals, upload them (JPG/PNG) into the third box for Physical Verification.

**Step 3: Execute the Audit**
1. Click the large blue **"EXECUTE VESSEL CLEARANCE AUDIT"** button.
2. The system will read the PDFs, extract the data using the selected LLM, run the 7-point reconciliation checks, and generate the report.

**Step 4: Review Dashboard & Resolve Discrepancies**
1. Once complete, review the **Dashboard** metrics to see your overall Documentation Integrity score.
2. Switch to the **"Actionable Discrepancies"** tab.
3. Expand any red (`❌`) or yellow (`⚠️`) warnings to see exactly what values mismatched between the documents.
4. To resolve a discrepancy, type a reason in the **"Override Reason"** box and click **"Acknowledge & Override"**. The dashboard will instantly recalculate to clear the error.

**Step 5: Export & Save**
1. Go back to the **Dashboard** tab.
2. Under "Export Reports", click the button to download the finalized report in your preferred format (Excel, HTML, or JSON).
3. Your audit is automatically saved. You can always retrieve it later by clicking on the **"Past Audits"** tab at the top of the page.
