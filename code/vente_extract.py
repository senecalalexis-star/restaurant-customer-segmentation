import os
import re
import csv
import unicodedata
from datetime import datetime
from pathlib import Path
import pdfplumber
import tempfile

# -------------------------
# CONFIG PATHS
# -------------------------
BASE_DIR = Path(r"D:\Vente_extract")
INPUT_DIR = BASE_DIR / "Input"
OUTPUT_DIR = BASE_DIR / "Output"
FEED_DIR = BASE_DIR / "Feed"

WEEK_TABLE = FEED_DIR / "week_id_table.csv"
ESCOMPTE_TABLE = FEED_DIR / "escompte.csv"
METHODE_TABLE = FEED_DIR / "methode_paiement.csv"

ESCOMPTE_CSV = OUTPUT_DIR / "escompte_sale.csv"
METHODE_CSV = OUTPUT_DIR / "methode_paiement_sale.csv"
TOTAL_CSV = OUTPUT_DIR / "total_sale.csv"

ESCOMPTE_FIELDS = ["week_id", "escompte_id", "number", "amount"]
METHODE_FIELDS = ["week_id", "methode_paiement_id", "number", "pourcentage"]
TOTAL_FIELDS = ["week_id", "total_before_escompte", "total_after_escompte", "t_p_s", "t_v_q", "total_sale"]

# -------------------------
# NORMALIZATION
# -------------------------
def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u00A0", " ")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"^\s*\d+\.\s*", "", s)
    s = s.replace("..", ".")
    s = s.replace(". ", ".")
    s = s.replace(" .", ".")
    s = re.sub(r"[^A-Za-z0-9 %\-.]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().upper()

# -------------------------
# CSV & LOOKUPS
# -------------------------
def load_week_table(path: Path):
    weeks = []
    if not path.exists():
        print(f"[ERROR] Week table not found: {path}")
        return weeks
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ws = r.get("week_start")
            we = r.get("week_end")
            wid = r.get("week_id") or r.get("id")
            if not (ws and we and wid):
                continue
            try:
                ws_dt = datetime.strptime(ws, "%Y-%m-%d %H:%M:%S")
                we_dt = datetime.strptime(we, "%Y-%m-%d %H:%M:%S")
            except:
                continue
            weeks.append({"week_id": wid, "week_start": ws_dt, "week_end": we_dt})
    return weeks

def load_lookup(path: Path, id_col: str, label_col: str, merge_cadeau=True):
    mapping = {}
    if not path.exists():
        print(f"[ERROR] Lookup missing: {path}")
        return mapping
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            _id = r.get(id_col)
            label = r.get(label_col)
            if not _id or label is None:
                continue
            norm = normalize_text(label)
            if merge_cadeau and "CADEAU" in norm:
                norm = re.sub(r"S?REFF$", "REFF", norm).strip()
            if norm not in mapping:
                mapping[norm] = _id
    return mapping

def ensure_csv(path: Path, fields):
    os.makedirs(path.parent, exist_ok=True)
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()

def load_existing_set(path: Path, key_cols):
    if not path.exists():
        return {}
    existing = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            key = tuple(r[c] for c in key_cols)
            existing[key] = r
    return existing

# -------------------------
# PDF HELPERS
# -------------------------
def parse_date_range(text: str):
    pat = re.compile(
        r"(\d{1,2}/\d{1,2}/\d{2})\s*@\s*(\d{1,2}:\d{2}).{0,30}(\d{1,2}/\d{1,2}/\d{2})\s*@\s*(\d{1,2}:\d{2})"
    )
    m = pat.search(text)
    if not m:
        return None, None

    def to_dt(d, t):
        dd, mm, yy = d.split("/")
        year = 2000 + int(yy)
        hh, mn = t.split(":")
        return datetime(year, int(mm), int(dd), int(hh), int(mn))

    try:
        return to_dt(m.group(1), m.group(2)), to_dt(m.group(3), m.group(4))
    except:
        return None, None

def match_week_id(start_dt, end_dt, weeks):
    if not start_dt or not end_dt:
        return None
    for w in weeks:
        if w["week_start"] == start_dt and w["week_end"] == end_dt:
            return w["week_id"]
    for w in weeks:
        if w["week_start"] <= start_dt <= w["week_end"]:
            return w["week_id"]
    return None

def write_unmatched(week_id: str, label: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{week_id}.txt"
    with open(path, "a", encoding="utf-8") as f:
        f.write(label + "\n")

# -------------------------
# NEW FIX — REMOVE ENTRAINEMENT SECTION
# -------------------------
def remove_entrainement_section(text: str) -> str:
    """
    Removes everything under 'Ventes entrainements'
    so that totals from that section are ignored.
    """
    lines = text.splitlines()
    cleaned = []
    skip = False
    for ln in lines:
        if "VENTES ENTRAINEMENT" in normalize_text(ln):
            skip = True
        if not skip:
            cleaned.append(ln)
    return "\n".join(cleaned)

# -------------------------
# ESCOMPTES
# -------------------------
ESC_LINE_RE = re.compile(
    r"""^\s*(?:\d+\.)?\s*
    ([A-Za-z0-9À-ÖØ-öø-ÿ\.\- /]+?)\s+
    (\d+)\s+
    \$\s*[-]?([\d,]+\.\d{2})
    """, re.X
)

def extract_escompte_block(text: str):
    lines = text.splitlines()
    start_idx = 0
    for i, ln in enumerate(lines):
        if "VENTES REGUL" in normalize_text(ln):
            start_idx = i
            break
    esc_idx = None
    for i in range(start_idx, len(lines)):
        if "ESCOMPTES" in normalize_text(lines[i]):
            esc_idx = i
            break
    if esc_idx is None:
        return []
    block = []
    for ln in lines[esc_idx + 1:]:
        if "TOTAL DES ESCOMPTES" in normalize_text(ln):
            break
        block.append(ln)
    return block

def parse_escompte_line(line: str):
    m = ESC_LINE_RE.match(line.strip())
    if not m:
        return None
    raw_label = m.group(1)
    number = int(m.group(2))
    amount = float(m.group(3).replace(",", ""))
    label = normalize_text(raw_label)
    return label, number, abs(amount)

# -------------------------
# PAIEMENT
# -------------------------
PAY_LINE_RE = re.compile(
    r"""^\s*(?:\d+\.)?\s*
    ([A-Za-z0-9À-ÖØ-öø-ÿ\.\- /]+?)\s+
    (\d+)\s+
    ([\d\.]+%)\s+
    \$[-]?([\d,]+\.\d{2})
    """, re.X
)

def extract_payment_block(text: str):
    lines = text.splitlines()
    start_idx = None
    for i, ln in enumerate(lines):
        if "MODES DE PAIEMENT GLOBAL" in normalize_text(ln):
            start_idx = i
            break
    if start_idx is None:
        return []
    header_idx = None
    for i in range(start_idx, len(lines)):
        if "DESCRIPTION" in normalize_text(lines[i]):
            header_idx = i
            break
    if header_idx is None:
        header_idx = start_idx
    block = []
    for ln in lines[header_idx + 1:]:
        if normalize_text(ln).startswith("TOTAL"):
            break
        block.append(ln)
    return block

def parse_payment_line(line: str):
    m = PAY_LINE_RE.match(line.strip())
    if not m:
        return None
    raw_label = m.group(1)
    number = int(m.group(2))
    percent = float(m.group(3).replace("%", "")) / 100.0
    label = normalize_text(raw_label)
    return label, number, percent

# -------------------------
# TOTALS
# -------------------------
def find_total_before_escompte(text: str):
    lines = text.splitlines()
    start_idx = None
    for i, ln in enumerate(lines):
        if "VENTES REGUL" in normalize_text(ln):
            start_idx = i
            break
    if start_idx is None:
        return None
    for ln in lines[start_idx:start_idx+40]:
        m = re.search(r"Sous-?total.*?\$?[-]?\s*([\d,]+\.\d{2})", ln, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))
    return None

def find_total_after_escompte(text: str):
    lines = text.splitlines()
    esc_total_idx = None
    for i, ln in enumerate(lines):
        if "TOTAL DES ESCOMPTE" in normalize_text(ln):
            esc_total_idx = i
            break
    if esc_total_idx is None:
        return None
    for ln in lines[esc_total_idx:esc_total_idx+30]:
        m = re.search(r"Sous-?total.*?\$?[-]?\s*([\d,]+\.\d{2})", ln, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))
    return None

def find_taxes_and_total(text: str):
    lines = text.splitlines()
    tps = None
    tvq = None
    total_sale = None

    for ln in lines:
        norm = normalize_text(ln)
        if "TPS" in norm or "T.P.S" in norm:
            m = re.search(r"\$?[-]?\s*([\d,]+\.\d{2})", ln)
            if m:
                tps = float(m.group(1).replace(",", ""))
        if "TVQ" in norm or "T.V.Q" in norm:
            m = re.search(r"\$?[-]?\s*([\d,]+\.\d{2})", ln)
            if m:
                tvq = float(m.group(1).replace(",", ""))

    tax_idx = None
    for i, ln in enumerate(lines):
        if "TPS" in normalize_text(ln) or "TVQ" in normalize_text(ln):
            tax_idx = i
            break

    if tax_idx is not None:
        for ln in lines[tax_idx:tax_idx+40]:
            if re.search(r"^\s*Total\b", ln, re.IGNORECASE):
                m = re.search(r"\$?[-]?\s*([\d,]+\.\d{2})", ln)
                if m:
                    total_sale = float(m.group(1).replace(",", ""))
                    break

    if total_sale is None:
        for ln in reversed(lines):
            if re.search(r"^\s*Total\b", ln, re.IGNORECASE):
                m = re.search(r"\$?[-]?\s*([\d,]+\.\d{2})", ln)
                if m:
                    total_sale = float(m.group(1).replace(",", ""))
                    break

    return tps, tvq, total_sale

# -------------------------
# MAIN PROCESS
# -------------------------
def process_all():
    print("[START] Processing PDFs...")

    ensure_csv(ESCOMPTE_CSV, ESCOMPTE_FIELDS)
    ensure_csv(METHODE_CSV, METHODE_FIELDS)
    ensure_csv(TOTAL_CSV, TOTAL_FIELDS)

    weeks = load_week_table(WEEK_TABLE)
    esc_map = load_lookup(ESCOMPTE_TABLE, "escompte_id", "escompte")
    pay_map = load_lookup(METHODE_TABLE, "methode_paiement_id", "methode_paiement")

    existing_esc = load_existing_set(ESCOMPTE_CSV, ESCOMPTE_FIELDS)
    existing_pay = load_existing_set(METHODE_CSV, METHODE_FIELDS)

    existing_totals = {}
    if TOTAL_CSV.exists():
        with open(TOTAL_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                existing_totals[r.get("week_id")] = r

    pdfs = sorted(INPUT_DIR.glob("*.pdf"))
    for pdf in pdfs:
        print(f"[PDF] {pdf.name}")
        try:
            with pdfplumber.open(str(pdf)) as doc:
                full_text = "\n".join(page.extract_text() or "" for page in doc.pages)
        except:
            continue

        start_dt, end_dt = parse_date_range(full_text)
        if not start_dt:
            continue

        week_id = match_week_id(start_dt, end_dt, weeks)
        if not week_id:
            continue

        # NEW FIX: Remove entrainement section before totals
        clean_text = remove_entrainement_section(full_text)

        # -------- ESCOMPTES --------
        esc_block = extract_escompte_block(full_text)
        for ln in esc_block:
            parsed = parse_escompte_line(ln)
            if not parsed:
                continue
            label, number, amount = parsed
            eid = esc_map.get(label)
            if not eid:
                write_unmatched(week_id, label)
                continue
            row = {
                "week_id": week_id,
                "escompte_id": eid,
                "number": str(number),
                "amount": f"{amount:.2f}"
            }
            key = (row["week_id"], row["escompte_id"], row["number"], row["amount"])
            if key not in existing_esc:
                with open(ESCOMPTE_CSV, "a", newline="", encoding="utf-8") as f:
                    csv.DictWriter(f, fieldnames=ESCOMPTE_FIELDS).writerow(row)
                existing_esc[key] = row

        # -------- PAIEMENT --------
        pay_block = extract_payment_block(full_text)
        for ln in pay_block:
            parsed = parse_payment_line(ln)
            if not parsed:
                continue
            label, number, percent = parsed
            mid = pay_map.get(label)
            if not mid:
                write_unmatched(week_id, label)
                continue
            row = {
                "week_id": week_id,
                "methode_paiement_id": mid,
                "number": str(number),
                "pourcentage": f"{percent:.4f}"
            }
            key = (row["week_id"], row["methode_paiement_id"], row["number"], row["pourcentage"])
            if key not in existing_pay:
                with open(METHODE_CSV, "a", newline="", encoding="utf-8") as f:
                    csv.DictWriter(f, fieldnames=METHODE_FIELDS).writerow(row)
                existing_pay[key] = row

        # -------- TOTALS --------
        tb = find_total_before_escompte(clean_text)
        ta = find_total_after_escompte(clean_text)
        tps, tvq, total_sale_val = find_taxes_and_total(clean_text)

        if any(v is not None for v in (tb, ta, tps, tvq, total_sale_val)):
            row = {
                "week_id": week_id,
                "total_before_escompte": f"{tb:.2f}" if tb is not None else "",
                "total_after_escompte": f"{ta:.2f}" if ta is not None else "",
                "t_p_s": f"{tps:.2f}" if tps is not None else "",
                "t_v_q": f"{tvq:.2f}" if tvq is not None else "",
                "total_sale": f"{total_sale_val:.2f}" if total_sale_val is not None else ""
            }
            existing_totals[week_id] = row

    temp_path = OUTPUT_DIR / (TOTAL_CSV.name + ".tmp")
    with open(temp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TOTAL_FIELDS)
        writer.writeheader()
        for wid in sorted(existing_totals.keys()):
            writer.writerow(existing_totals[wid])

    os.replace(str(temp_path), str(TOTAL_CSV))
    print("[FINISHED] All PDFs processed.")

if __name__ == "__main__":
    process_all()
