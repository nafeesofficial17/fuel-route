from pathlib import Path
import sys

pdf_path = Path(r"e:\MyProjects\New folder\Job title_ Django Developer _ Remote.pdf")
if not pdf_path.exists():
    print(f"PDF not found: {pdf_path}")
    sys.exit(1)

try:
    from pypdf import PdfReader
except Exception as e:
    print("MISSING_LIB")
    print(e)
    sys.exit(2)

reader = PdfReader(str(pdf_path))
text_parts = []
for page in reader.pages:
    try:
        text = page.extract_text()
    except Exception:
        text = None
    if text:
        text_parts.append(text)

text = "\n\n".join(text_parts)
print(text)
