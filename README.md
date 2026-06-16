# TradeProof

Intelligent Trade Document Reconciliation Platform. Instant. Accurate. Audit-Ready.

## Overview
TradeProof is a Python web application that accepts PDF uploads of an Ocean Bill of Lading (BL) and multiple Shipping Bills (SBs), extracts and normalizes the data using the Google Gemini API, and executes a 7-step reconciliation engine comparing the BL against all SBs. The results are displayed in a professional Streamlit dashboard and can be exported as HTML or JSON reports.

## Prerequisites
- Python 3.11+
- Google Gemini API Key

## Setup Instructions

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
Create a `.env` file from the example or set the `GEMINI_API_KEY` in the application sidebar.
```bash
cp .env.example .env
# Edit .env and add your API key
```

3. Run the application:
```bash
streamlit run app.py
```

## Features
- **Intelligent Extraction**: Uses Gemini API to extract structured data from trade documents.
- **7-Step Reconciliation**: 
  - Identifier Matching
  - SB Documentation
  - Package Count Aggregation
  - Gross Weight Aggregation
  - Container & Seal Verification
  - HS Classification
  - Invoice Reconciliation
- **Detailed Reporting**: Generates interactive HTML and JSON reports.
