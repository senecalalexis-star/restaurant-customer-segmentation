import os
import pdfplumber
import re
import pandas as pd
import unicodedata
from datetime import datetime

# === CONFIGURATION ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FOLDER = SCRIPT_DIR                # PDFs in same folder
OUTPUT_FOLDER = os.path.join(SCRIPT_DIR, "Output")
ITEM_ID_FILE = os.path.join(SCRIPT_DIR, "item_id.csv")
WEEK_ID_FILE = os.path.join(SCRIPT_DIR, "week_id_table.csv")  # UPDATED

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Regex to capture date line like: 1/06/25 @ 4:00 -> 8/06/25 @ 3:59
DATE_LINE_PATTERN = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{2})\s*@\s*(\d{1,2}:\d{2})\s*->\s*(\d{1,2}/\d{1,2}/\d{2})\s*@\s*(\d{1,2}:\d{2})"
)

# Regex for valid item lines
LINE_PATTERN = re.compile(r"^\s*(.+?)\s+([\d\.]+)\s+\$[\d\.,]+", re.MULTILINE)

# FIXED — Normalize STOP_TEXT to match normalized PDF text
def normalize(text):
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFD", text)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.upper().strip()

STOP_TEXT = normalize("VENTES PAR ITEMS PAR EMPLOYÉS")

BLACKLIST = {
    "TOTAL", "GRAND-TOTAL", "J'ENLEVE", "MESSAGE", "SANS ALCOOL", "FUMFUM",
    "VARIANTES NOURRITURE", "TAPAS ET ENTREE", "LES GROS CREUX", "MENU ENFANTS",
    "EXTRAS", "DESSERTS", "BIERES FUT", "MICROS INVITEES", "VINS BLANCS",
    "VINS ROUGES", "ALCOOL", "COCKTAILS", "SHOOTERS", "KOMBUCHA",
    "MOCKTAILS", "LOCATIONS", "CUISINE", "HEBERGMENT", "BAR",
    "DIVERS BOISSON", "DIVERS NOURRITURE", "BOISSONS CHAUDES", 
    "MENU FIN DE SOIREE", "AUTRES VENTES.", "VINS ROSES", "LAVAGE ET DOUCHE", "CHASER", "NOM CLIENT", "GLACE",
    "PRIVATISATION AUBERGE"

}

# Load item ID table
def load_item_id_table():
    if not os.path.exists(ITEM_ID_FILE):
        print("WARNING: item_id.csv not found. No matching will be done.")
        return {}

    df = pd.read_csv(ITEM_ID_FILE)
    df["clean_name"] = df["name"].astype(str).apply(normalize)

    return dict(zip(df["clean_name"], df["item_id"]))

ITEM_LOOKUP = load_item_id_table()

# Load week_id lookup table
def load_week_lookup():
    if not os.path.exists(WEEK_ID_FILE):
        print("ERROR: week_id_table.csv not found!")
        return None

    df = pd.read_csv(WEEK_ID_FILE)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["week_end"] = pd.to_datetime(df["week_end"])
    return df

WEEK_TABLE = load_week_lookup()

def detect_week_id(pdf_text):
    m = DATE_LINE_PATTERN.search(pdf_text)
    if not m:
        print("WARNING: No date range detected in PDF.")
        return None

    start_date_raw, start_time_raw, end_date_raw, end_time_raw = m.groups()

    start_dt = datetime.strptime(start_date_raw + " " + start_time_raw, "%d/%m/%y %H:%M")
    end_dt = datetime.strptime(end_date_raw + " " + end_time_raw, "%d/%m/%y %H:%M")

    match = WEEK_TABLE[
        (WEEK_TABLE["week_start"] == start_dt) &
        (WEEK_TABLE["week_end"] == end_dt)
    ]

    if match.empty:
        print(f"WARNING: No matching week_id found for range {start_dt} -> {end_dt}")
        return None

    return int(match.iloc[0]["week_id"])

def extract_items_from_pdf(pdf_path):
    text_raw = ""
    text_normalized = ""
    missing_items = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if not extracted:
                continue

            text_raw += extracted + "\n"
            norm = normalize(extracted)

            # FIX: STOP correctly when encountering the STOP_TEXT
            if STOP_TEXT in norm:
                text_normalized += norm[:norm.index(STOP_TEXT)]
                break
            else:
                text_normalized += norm + "\n"

    week_id = detect_week_id(text_raw)

    rows = []

    for m in LINE_PATTERN.finditer(text_normalized):
        item_name = m.group(1).strip()
        quantity = float(m.group(2))

        clean_item = normalize(item_name)

        if clean_item in BLACKLIST:
            continue

        # Skip headers like "10.BLAH"
        if re.match(r"^\d+\.\w+", item_name):
            continue

        if clean_item in ITEM_LOOKUP:
            item_output = ITEM_LOOKUP[clean_item]
        else:
            if item_name not in missing_items:
                missing_items.append(item_name)
            continue

        rows.append([item_output, quantity])

    return week_id, rows, missing_items

def process_all_pdfs():
    for filename in os.listdir(INPUT_FOLDER):
        if not filename.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(INPUT_FOLDER, filename)
        csv_name = os.path.splitext(filename)[0] + ".csv"

        print(f"\nProcessing: {filename}")

        week_id, data, missing_items = extract_items_from_pdf(pdf_path)

        df = pd.DataFrame(data, columns=["item_id", "quantity"])
        df = df.groupby("item_id", as_index=False)["quantity"].sum()
        df.insert(0, "week_id", week_id)

        out_csv = os.path.join(OUTPUT_FOLDER, csv_name)
        df.to_csv(out_csv, index=False, encoding="utf-8-sig")
        print(f"Saved: {out_csv}")

        if missing_items:
            missing_file = os.path.join(
                OUTPUT_FOLDER,
                f"{os.path.splitext(filename)[0]}_missing_items.txt"
            )
            with open(missing_file, "w", encoding="utf-8") as f:
                for name in missing_items:
                    f.write(name + "\n")

            print(f"Missing items saved: {missing_file}")
        else:
            print("No missing items.")

if __name__ == "__main__":
    process_all_pdfs()
    print("\n=== Extraction Complete ===")
