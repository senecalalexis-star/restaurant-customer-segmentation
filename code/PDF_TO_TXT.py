import os
import re
from PyPDF2 import PdfReader

# --------------------------------------------------------
# PATHS
# --------------------------------------------------------

input_folder = r"D:\BASE CAMP TOOL\item_extract_fool_bill\Input"
output_folder = r"D:\BASE CAMP TOOL\item_extract_fool_bill\Process"
output_file = os.path.join(output_folder, "pdf_to_text.txt")

# --------------------------------------------------------
# FIND THE PDF FILE (only one expected in the folder)
# --------------------------------------------------------

pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith(".pdf")]

if not pdf_files:
    raise FileNotFoundError("No PDF file found in the Input folder.")

pdf_path = os.path.join(input_folder, pdf_files[0])

# --------------------------------------------------------
# EXTRACT TEXT FROM PDF
# --------------------------------------------------------

reader = PdfReader(pdf_path)
all_text = ""

for page in reader.pages:
    all_text += page.extract_text() + "\n"

# --------------------------------------------------------
# CLEAN LINES
# --------------------------------------------------------

cleaned_lines = []
for line in all_text.splitlines():

    # Remove blank lines
    if not line.strip():
        continue

    # 1. Remove date/time + PAGE header
    #    Example: "1/12/25 19:41 ... PAGE 1"
    if re.match(r"^\d{1,2}/\d{1,2}/\d{2}.*PAGE\s+\d+", line):
        continue

    # 2. Remove "AUBERGE LE CAMP DE BASE"
    if line.strip() == "AUBERGE LE CAMP DE BASE":
        continue

    # 3. Remove "Veloce X.XX.XX"
    if line.strip().startswith("Veloce"):
        continue

    # Otherwise keep the line (in same order)
    cleaned_lines.append(line.strip())

# --------------------------------------------------------
# WRITE TO OUTPUT TXT
# --------------------------------------------------------

with open(output_file, "w", encoding="utf-8") as f:
    for line in cleaned_lines:
        f.write(line + "\n")

print(f"Done! Cleaned text saved to:\n{output_file}")
