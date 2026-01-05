import os
import re
import csv
from datetime import datetime

# ----------------------------------------------------
#  PATHS
# ----------------------------------------------------
INPUT_TXT = r"D:\BASE CAMP TOOL\item_extract_fool_bill\Process\pdf_to_text.txt"
OUTPUT_CSV = r"D:\BASE CAMP TOOL\item_extract_fool_bill\Process\bill_id.csv"
MISSING_NAMES = r"D:\BASE CAMP TOOL\item_extract_fool_bill\Process\missing_name.txt"
EMPLOYEE_TABLE = r"D:\TABLE FINAL\Employee.csv"

# ----------------------------------------------------
#  LOAD EMPLOYEE TABLE (name → employee_id)
# ----------------------------------------------------
employee_map = {}

with open(EMPLOYEE_TABLE, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        employee_map[row["name"].strip().upper()] = row["employee_id"]

# ----------------------------------------------------
#  PATTERNS
# ----------------------------------------------------
server_pattern = re.compile(r"^\d{1,3}\.[A-Za-zÀ-ÖØ-öø-ÿ \-']+$")
date_pattern = re.compile(r"^\d{1,2}/\d{1,2}/\d{2}\s+\d{1,2}:\d{2}$")
bill_id_pattern = re.compile(r"(\d{5})\s*\(\d{5}\)")
table_pattern = re.compile(r"Table#(\d+)", re.IGNORECASE)

# ----------------------------------------------------
#  READ INPUT TXT
# ----------------------------------------------------
with open(INPUT_TXT, "r", encoding="utf-8") as f:
    lines = [line.strip() for line in f]

records = []
missing_server_names = []

# ----------------------------------------------------
#  PROCESS LINES
# ----------------------------------------------------
for i, line in enumerate(lines):

    # ----------- FIND DATE LINE -----------
    if date_pattern.match(line):

        raw_dt = line.strip()
        parts = raw_dt.split()

        date_part = parts[0]
        time_part = parts[1]

        # zero-pad hour
        hour = time_part.split(":")[0]
        if len(hour) == 1:
            time_part = "0" + time_part

        # convert to datetime
        dt = datetime.strptime(f"{date_part} {time_part}", "%d/%m/%y %H:%M")

        sql_date = dt.strftime("%Y-%m-%d")
        sql_time = dt.strftime("%H:%M:%S")

        # ----------- SERVER NAME ABOVE DATE -----------
        employee_id = None

        if i > 0 and server_pattern.match(lines[i - 1]):
            raw_server = lines[i - 1].split(".", 1)[1].strip().upper()

            if raw_server in employee_map:
                employee_id = employee_map[raw_server]
            else:
                missing_server_names.append(raw_server)

        # ----------- FIND BILL ID + TABLE ID + REDISTRIBUTION -----------
        bill_id = None
        table_id = 0
        is_redistribuee = False

        for j in range(i + 1, min(i + 6, len(lines))):
            line_check = lines[j]

            # look for bill id
            match = bill_id_pattern.search(line_check)
            if match:
                bill_id = match.group(1)

                # table id
                tmatch = table_pattern.search(line_check)
                if tmatch:
                    table_id = int(tmatch.group(1))

                # check if next line is Redistribuée
                if j + 1 < len(lines) and lines[j + 1].strip().upper() == "REDISTRIBUÉE":
                    is_redistribuee = True
                else:
                    is_redistribuee = False

                break

        # ----------- SAVE ROW -----------
        if bill_id:
            records.append({
                "bill_id": bill_id,
                "employee_id": employee_id,
                "table_id": table_id,
                "date": sql_date,
                "time": sql_time,
                "is_redistribuee": is_redistribuee
            })

# ----------------------------------------------------
#  WRITE CSV
# ----------------------------------------------------
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["bill_id", "employee_id", "table_id", "date", "time", "is_redistribuee"]
    )
    writer.writeheader()
    writer.writerows(records)

# ----------------------------------------------------
#  WRITE missing_name.txt
# ----------------------------------------------------
if missing_server_names:
    with open(MISSING_NAMES, "w", encoding="utf-8") as f:
        for name in sorted(set(missing_server_names)):
            f.write(name + "\n")

print("Processing complete.")
print(f"CSV saved → {OUTPUT_CSV}")
print(f"Missing names saved → {MISSING_NAMES}")
