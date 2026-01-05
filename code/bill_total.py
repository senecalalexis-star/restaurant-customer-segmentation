import os
import re
import csv

# ----------------------------------------------------
# PATHS
# ----------------------------------------------------
INPUT_TXT = r"D:\BASE CAMP TOOL\item_extract_fool_bill\Process\pdf_to_text.txt"
OUTPUT_CSV = r"D:\BASE CAMP TOOL\item_extract_fool_bill\Process\bill_total.csv"

# ----------------------------------------------------
# BILL ID PATTERN (same as your other script)
# ----------------------------------------------------
bill_id_pattern = re.compile(r"(\d{5})\s*\(\d{5}\)")

# ----------------------------------------------------
# UPDATED TOTAL PATTERN (case-insensitive + flexible spaces)
# Example: "Total                                         $6.90"
# ----------------------------------------------------
total_pattern = re.compile(r"^TOTAL\s+.*?([\d]+\.\d{2})", re.IGNORECASE)

# ----------------------------------------------------
# MATCH PAYMENT LINE (any line ending with a money amount)
# e.g. "3.VISA                       $19.84"
# ----------------------------------------------------
payment_pattern = re.compile(r"([\d]+\.\d{2})\s*$")

# ----------------------------------------------------
# READ FILE
# ----------------------------------------------------
with open(INPUT_TXT, "r", encoding="utf-8") as f:
    lines = [line.rstrip("\n") for line in f]

records = []
current_bill_id = None
waiting_for_total = False
last_total_amount = None

# ----------------------------------------------------
# MAIN LOOP
# ----------------------------------------------------
for i, line in enumerate(lines):

    # ------------------------------
    # Detect NEW bill_id
    # ------------------------------
    match = bill_id_pattern.search(line)
    if match:
        current_bill_id = match.group(1)
        waiting_for_total = True
        last_total_amount = None
        continue

    if not waiting_for_total:
        continue

    # ------------------------------
    # Detect TOTAL line
    # ------------------------------
    t = total_pattern.search(line)
    if t:
        total_amount = float(t.group(1))
        last_total_amount = total_amount

        # Check next line for payment amount
        payment = 0.0
        tip_percent = 0.0

        if i + 1 < len(lines):
            next_line = lines[i + 1]
            p = payment_pattern.search(next_line)

            if p:
                payment = float(p.group(1))

                # calculate tip percent
                if total_amount > 0:
                    tip_percent = ((payment - total_amount) / total_amount)
                    tip_percent = round(tip_percent, 2)

                # -----------------------------------------
                # NEW RULE: if tip_percent is negative → 0
                # -----------------------------------------
                if tip_percent < 0:
                    tip_percent = 0.0

        # ----------------------------------------------------
        # Save record with specified column names
        # ----------------------------------------------------
        records.append({
            "bill_id": current_bill_id,
            "total": f"{total_amount:.2f}",
            "payment": f"{payment:.2f}",
            "tip_percent": f"{tip_percent:.2f}"
        })

        waiting_for_total = False
        continue


# ----------------------------------------------------
# WRITE CSV
# ----------------------------------------------------
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["bill_id", "total", "payment", "tip_percent"])
    writer.writeheader()
    writer.writerows(records)

print("DONE!")
print(f"bill_total.csv created → {OUTPUT_CSV}")
