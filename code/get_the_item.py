import os
import re
import csv
import unicodedata

# ----------------------------------------------------
# PATHS
# ----------------------------------------------------
INPUT_TXT = r"D:\BASE CAMP TOOL\item_extract_fool_bill\Process\pdf_to_text.txt"
ITEM_TABLE = r"D:\TABLE FINAL\item_id.csv"
OUTPUT_CSV = r"D:\BASE CAMP TOOL\item_extract_fool_bill\Process\bill_items.csv"
MISSING_TXT = r"D:\BASE CAMP TOOL\item_extract_fool_bill\Process\missing_items.txt"

# ----------------------------------------------------
# HELPERS
# ----------------------------------------------------
def normalize(s):
    """Uppercase, remove accents, collapse spaces."""
    if not s:
        return ""
    s = s.upper()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("’", "'").replace("`", "'")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def similarity(a, b):
    """Simple fuzzy match."""
    ta = set(a.split())
    tb = set(b.split())
    if not ta or not tb:
        return 0
    inter = len(ta & tb)
    union = len(ta | tb)
    token_score = inter / union
    shorter = min(len(a), len(b))
    if shorter == 0:
        char_score = 0
    else:
        same_chars = sum(1 for x, y in zip(a, b) if x == y)
        char_score = same_chars / shorter
    return (token_score * 0.65) + (char_score * 0.35)


def prefix_ratio(a, b):
    max_len = min(len(a), len(b))
    prefix_len = 0
    for i in range(max_len):
        if a[i] == b[i]:
            prefix_len += 1
        else:
            break
    return prefix_len / max_len if max_len > 0 else 0


FUZZY_THRESHOLD = 0.88
PREFIX_THRESHOLD = 0.70

# ----------------------------------------------------
# LOAD ITEM TABLE
# ----------------------------------------------------
item_map = {}
item_list = []

with open(ITEM_TABLE, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        norm = normalize(row["name"])
        item_map[norm] = row["item_id"]
        item_list.append((norm, row["item_id"]))

# ----------------------------------------------------
# PATTERNS
# ----------------------------------------------------
bill_id_pattern = re.compile(r"(\d{5})\s*\(\d{5}\)")
fp_pattern = re.compile(r"FP\s*$")

# ----------------------------------------------------
# READ TXT
# ----------------------------------------------------
with open(INPUT_TXT, "r", encoding="utf-8") as f:
    lines = [line.rstrip("\n") for line in f]

records = []
missing_items = []
current_bill_id = None

# ----------------------------------------------------
# MAIN LOOP
# ----------------------------------------------------
for i, line in enumerate(lines):

    match = bill_id_pattern.search(line)
    if match:
        current_bill_id = match.group(1)
        continue

    if current_bill_id is None:
        continue

    if not fp_pattern.search(line):
        continue

    raw = line.strip()
    parts = raw.split()
    if len(parts) < 2:
        continue

    # ------------------------------------------------
    # NEW FEATURE: extract quantity
    # ------------------------------------------------
    quantity_raw = parts[0]

    # Convert qty to float safely
    try:
        quantity = float(quantity_raw)
    except:
        quantity = 1  # fallback

    # extract item name after qty
    after_qty = raw[len(parts[0]):].strip()

    if "/" in after_qty:
        before, after = after_qty.split("/", 1)
        item_name = after.strip()
        if " $" in item_name:
            item_name = item_name.split(" $")[0].strip()
        if "  $" in item_name:
            item_name = item_name.split("  $")[0].strip()
    else:
        if " $" in after_qty:
            item_name = after_qty.split(" $")[0].strip()
        elif "  $" in after_qty:
            item_name = after_qty.split("  $")[0].strip()
        else:
            item_name = after_qty.strip()

    norm_item = normalize(item_name)

    # ------------------------------------------------
    # STEP 1 — Exact match
    # ------------------------------------------------
    item_id = item_map.get(norm_item)

    # ------------------------------------------------
    # STEP 2 — Fuzzy
    # ------------------------------------------------
    if item_id is None:
        best_score = 0
        best_id = None
        for ref_name, ref_id in item_list:
            score = similarity(norm_item, ref_name)
            if score > best_score:
                best_score = score
                best_id = ref_id
        if best_score >= FUZZY_THRESHOLD:
            item_id = best_id

    # ------------------------------------------------
    # STEP 3 — Prefix rule
    # ------------------------------------------------
    if item_id is None:
        best_prefix = 0
        best_id = None
        for ref_name, ref_id in item_list:
            pr = prefix_ratio(norm_item, ref_name)
            if pr > best_prefix:
                best_prefix = pr
                best_id = ref_id
        if best_prefix >= PREFIX_THRESHOLD:
            item_id = best_id

    # ------------------------------------------------
    # SAVE
    # ------------------------------------------------
    if item_id is not None:
        records.append({
            "bill_id": current_bill_id,
            "item_id": item_id,
            "quantity": quantity     # ← NEW COLUMN
        })
    else:
        missing_items.append(item_name)

# ----------------------------------------------------
# WRITE CSV
# ----------------------------------------------------
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["bill_id", "item_id", "quantity"])
    writer.writeheader()
    writer.writerows(records)

# ----------------------------------------------------
# WRITE missing_items.txt
# ----------------------------------------------------
with open(MISSING_TXT, "w", encoding="utf-8") as f:
    for m in sorted(set(missing_items)):
        f.write(m + "\n")

print("DONE!")
print(f"bill_items.csv → {OUTPUT_CSV}")
print(f"missing_items.txt → {MISSING_TXT}")
