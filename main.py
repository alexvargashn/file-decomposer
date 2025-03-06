from io import BytesIO
import tempfile
from typing import Union

from fastapi import FastAPI, File, UploadFile
from pathlib import Path
import pdfplumber

app = FastAPI()

MAX_MEMORY_SIZE = 10


# Entry point for example proposes
@app.get("/")
def read_root():
    return {"Hello": "World"}


# Handle PDF operations
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

    # Process the PDF file
    with pdfplumber.open(
        str(pdf_stream) if isinstance(pdf_stream, Path) else pdf_stream
    ) as pdf:
        text = "\n".join([page.extract_text() or "" for page in pdf.pages])

    return {"filename": file.filename, "size": size, "content": text}
