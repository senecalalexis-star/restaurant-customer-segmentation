import os
import re
import pdfplumber
import pandas as pd
import unicodedata

# ---------------- CONFIG ----------------
SCRIPT_DIR = r"D:\Get_price"
INPUT_FOLDER = SCRIPT_DIR
ITEM_ID_FILE = os.path.join(SCRIPT_DIR, "item_id.csv")

# Regex to detect item lines
LINE_PATTERN = re.compile(r"^\s*(.+?)\s+([\d\.]+)\s+\$([\d\.,]+)", re.MULTILINE)

# Blacklist (same as your first script)
BLACKLIST = {
    "TOTAL", "GRAND-TOTAL", "J'ENLEVE", "MESSAGE", "SANS ALCOOL", "FUMFUM",
    "VARIANTES NOURRITURE", "TAPAS ET ENTREE", "LES GROS CREUX", "MENU ENFANTS",
    "EXTRAS", "DESSERTS", "BIERES FUT", "MICROS INVITEES", "VINS BLANCS",
    "VINS ROUGES", "ALCOOL", "COCKTAILS", "SHOOTERS", "KOMBUCHA",
    "MOCKTAILS", "LOCATIONS", "CUISINE", "HEBERGMENT", "BAR",
    "DIVERS BOISSON", "DIVERS NOURRITURE", "BOISSONS CHAUDES","MENU FIN DE SOIREE",
    "AUTRES VENTES.","VINS ROSES", "LAVAGE ET DOUCHE", "CHASER", "NOM CLIENT", "GLACE",
    "PRIVATISATION AUBERGE"

}

# ---------- Utility ----------

def normalize(text):
    """Remove accents, uppercase, strip spaces."""
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFD", text)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.upper().strip()

# ---------- Load item_id.csv ----------

def load_item_table():
    if not os.path.exists(ITEM_ID_FILE):
        raise FileNotFoundError("item_id.csv not found in D:\\Get_price")

    df = pd.read_csv(ITEM_ID_FILE)

    # Add price column if missing
    if "price" not in df.columns:
        df["price"] = None

    # Build lookup dictionary (normalized name → row index)
    lookup = {}
    for idx, row in df.iterrows():
        if isinstance(row["name"], str):
            lookup[normalize(row["name"])] = idx

    return df, lookup

# ---------- Extract from PDF ----------

def extract_prices_from_pdf(pdf_path):
    """Return a list of (item_name, unit_price)."""
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"

    results = []

    for match in LINE_PATTERN.finditer(text):
        item_name = match.group(1).strip()
        quantity = float(match.group(2))
        total_price = float(match.group(3).replace(",", ""))

        clean_item = normalize(item_name)

        if clean_item in BLACKLIST:
            continue

        # Ignore category headers like "12.SOMETHING"
        if re.match(r"^\d+\.\w+", item_name):
            continue

        # Compute unit price
        if quantity > 0:
            unit_price = round(total_price / quantity, 2)
        else:
            continue

        results.append((item_name, unit_price))

    return results

# ---------- MAIN ----------

def main():
    df, lookup = load_item_table()

    print("Scanning PDFs in:", INPUT_FOLDER)
    pdf_files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print("No PDF files found.")
        return

    for filename in pdf_files:
        pdf_path = os.path.join(INPUT_FOLDER, filename)
        print(f"\nProcessing {filename} ...")

        extracted_items = extract_prices_from_pdf(pdf_path)

        for item_name, price in extracted_items:
            clean_name = normalize(item_name)

            if clean_name not in lookup:
                print(f" → Item NOT found in item_id.csv: {item_name}")
                continue

            row = lookup[clean_name]

            # DO NOT OVERWRITE EXISTING PRICES
            existing_price = df.at[row, "price"]
            if pd.notna(existing_price):
                print(f" → SKIPPED {item_name}: price already exists ({existing_price})")
                continue

            # Update price only if empty
            df.at[row, "price"] = price
            print(f" → Added price for {item_name}: {price}")

    # Save updated CSV
    df.to_csv(ITEM_ID_FILE, index=False, encoding="utf-8-sig")
    print("\n✅ item_id.csv updated successfully (no overwriting).")

if __name__ == "__main__":
    main()
