import re
from io import BytesIO
import tempfile
from typing import Union
from fastapi import FastAPI, File, UploadFile
from pathlib import Path
import pdfplumber

app = FastAPI()
MAX_MEMORY_SIZE = 10


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.post("/pdf")
async def handle_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        return {"error": "Only PDF files are allowed for this endpoint"}

    size = file.size / 1024 / 1024
    content = await file.read()
    if size < MAX_MEMORY_SIZE:
        pdf_stream = BytesIO(content)  # In memory
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            pdf_stream = Path(tmp.name)  # On disk

    text = extract_text_from_pdf(pdf_stream)
    sections = split_into_sections(text)

    return {"filename": file.filename, "size": size, "content": sections}


def extract_text_from_pdf(file: Union[Path, BytesIO]) -> str:
    with pdfplumber.open(str(file) if isinstance(file, Path) else file) as pdf:
        return "\n".join([page.extract_text() or "" for page in pdf.pages])


def split_into_sections(text: str):
    # Search and find the books and its content
    sections = []
    books_pattern = r"^(LIBRO|LBRO)\s+[^\n]*(?:\n(.+?))?(?=\n(?:(LIBRO|LBRO))|\Z)"
    books_matched = re.finditer(books_pattern, text, re.MULTILINE | re.DOTALL)
    for match in books_matched:
        book_title = match.group(0).split("\n")[0]
        book_description = get_book_description(match.group(2).strip)
        book_content = match.group(2).strip()
        sections.append(
            {
                "title": book_title,
                "description": get_book_description(book_content),
                "content": book_content,
            }
        )
    return sections


def get_book_description(text: str):
    stop_pattern = r"^(TITULO|ARTICULO|CAPITULO)\b"

    # Search the first occurrence of the stop pattern
    match = re.search(stop_pattern, text, re.MULTILINE)

    if match:
        return text[
            : match.start()
        ].strip()  # Extract the description before the stop pattern
    return text.strip()  # If no stop pattern is found, return the whole text
