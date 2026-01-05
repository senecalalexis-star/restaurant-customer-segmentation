# Data Engineering & ETL Pipeline

This project utilizes a custom-built Python ETL ecosystem to transform unstructured restaurant data (PDFs) into a normalized SQL database. The architecture is split into four modules.

## 1. Automated Sales ETL
**File:** `code/extract_sales.py`

This script serves as the primary **ETL (Extract, Transform, Load)** tool for the project. It automates the ingestion of unstructured data from the restaurant's Point-of-Sale (POS) system, converting PDF reports into clean, database-ready CSV files.

**Key Technical Features:**
* **PDF Parsing:** Utilizes `pdfplumber` to extract raw text from layout-heavy PDF reports.
* **Regex Pattern Matching:** Automatically detects the report's date range (e.g., `1/08/25 @ 4:00 -> 8/08/25 @ 3:59`) and queries a `week_id` lookup table to assign the correct fiscal week ID.
* **Robust String Normalization:** Handles Unicode normalization (NFD) to strip accents and standardize French text (e.g., `HÉBERGMENT` -> `HEBERGMENT`) for accurate ID matching.
* **Data Quality Safety Net:** Any item found in the PDF that does not exist in the `item_id` database is automatically flagged and exported to a `missing_items.txt` file, ensuring 100% data integrity before SQL import.

**Libraries Used:** `pandas`, `pdfplumber`, `re`, `unicodedata`, `os`.

---

## 2. Financial Data Parser
**File:** `code/extract_finance.py`

This advanced ETL script extracts high-level financial metrics from the same POS PDF reports. Unlike the item-level extractor, this script parses unstructured blocks of text to isolate three distinct financial datasets: **Discounts**, **Payment Methods**, and **Weekly Totals**.

**Key Technical Features:**
* **Multi-Section Parsing:** Intelligently identifies and isolates specific text blocks (e.g., "MODES DE PAIEMENT GLOBAL" vs. "VENTES REGUL") to extract data into three separate CSV outputs simultaneously.
* **Financial Integrity Logic:**
    * **"Entrainement" Exclusion:** Automatically detects and removes training/staff meal transactions ("VENTES ENTRAINEMENT") from the text stream *before* calculating totals to prevent revenue inflation.
    * **Tax & Revenue Validation:** Captures `Total Before Discount`, `Total After Discount`, `TPS`, `TVQ`, and `Grand Total` separately to allow for downstream reconciliation in SQL.
* **Dynamic Mapping System:** Uses fuzzy string normalization to map French payment descriptions (e.g., "CADEAU REFF" vs. "CADEAU") to a standardized `methode_id`, creating a new `.txt` log file for any unknown payment types requiring manual review.

**Outputs:**
* `escompte_sale.csv`: breakdown of discounts given.
* `methode_paiement_sale.csv`: distribution of payment types.
* `total_sale.csv`: the "Source of Truth" for weekly revenue validation.

**Libraries Used:** `pdfplumber`, `re` (Regex), `csv`, `unicodedata`, `pathlib`.

---

## 3. Automated Price Derivation 
**File:** `code/get_price.py`

This script functions as a **Dimension Enrichment** tool. It solves a key data gap by retroactively populating the master `item_id` dimension table with unit prices derived from historical sales reports. Since the raw POS data only provided aggregate totals, this script reverse-engineers the unit price for every item.

**Key Technical Features:**
* **Metric Derivation:** Calculates the `Unit Price` by parsing sales lines (`Total Revenue / Quantity Sold`) rather than scraping a static menu, ensuring prices reflect actual transaction history.
* **Non-Destructive Update Logic:** Implements a safety check that **only** fills missing values (`NULL` prices). It explicitly skips items that already have a price, preserving any manual overrides or historical data already present in the database.
* **Master Data Management (MDM):** Updates the central `item_id.csv` source of truth directly, ensuring that all downstream SQL analysis (like Revenue Estimations) has access to accurate pricing context.

**Libraries Used:** `pandas`, `pdfplumber`, `re`, `unicodedata`.

---

## 4. High-Volume Transaction Pipeline
**Module:** `code/bill_processing_pipeline/`

This multi-stage engineering pipeline is designed to ingest and structure thousands of raw PDF receipts into a relational database format. It decomposes the ETL process into four specialized scripts to ensure data integrity across dimensions (Time, Staff, Finance, and Inventory).

**Pipeline Stages:**

1.  **Pre-processing (PDF $\rightarrow$ TXT):**
    * **Script:** `pdf_to_text.py`
    * **Logic:** Uses `PyPDF2` to strip noise (headers, page numbers) and convert unstructured PDF binaries into clean, line-by-line text streams for downstream parsing.

2.  **Metadata & Staff Extraction:**
    * **Script:** `extract_bill_header.py`
    * **Logic:** Harvests the "Fact Table" skeleton (`Bill ID`, `Table #`, `Timestamp`). It also performs a lookup against the `Employee` table to link every bill to a specific server ID, flagging unknown names for manual review.

3.  **Item Normalization (The "Fuzzy" Matcher):**
    * **Script:** `extract_items.py`
    * **Logic:** Parses line items and quantities.
    * **Algorithm:** Implements a custom **Weighted Fuzzy Matching** algorithm (65% Token Score + 35% Character Score) to map messy receipt text (e.g., "BURGER..") to the clean `item_id` database key. It falls back to a "Prefix Ratio" check if fuzzy matching fails.

4.  **Financial Reconciliation:**
    * **Script:** `extract_totals.py`
    * **Logic:** Extracts the final `Total Amount` and `Payment Amount` to calculate the **Tip Percentage** for each transaction, enabling service quality analysis.

**Key Technical Decision:**
* **Decoupled Architecture:** Splitting "Header," "Items," and "Totals" into separate parsers allows the pipeline to handle partial failures (e.g., if a tip calculation fails, the item sales data is still preserved).

**Libraries Used:** `PyPDF2`, `re`, `unicodedata`, `csv`, `os`.
