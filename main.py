from queue import Full
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
    sections = parse_legal_document(text)

    return {"filename": file.filename, "size": size, "content": sections}


def extract_text_from_pdf(file: Union[Path, BytesIO]) -> str:
    with pdfplumber.open(str(file) if isinstance(file, Path) else file) as pdf:
        return "\n".join([page.extract_text() or "" for page in pdf.pages])


from typing import List


def split_into_sections(
    text: str, titles: List[str], sections_name="title", have_content=False
):
    # Search and find the books and its content
    titles_to_find = "|".join(titles)
    sections = []
    sections_pattern = (
        rf"^({titles_to_find})\s+[^\n]*(?:\n(.+?))?(?=\n(?:{titles_to_find})|\Z)"
    )
    sects_matches = re.finditer(sections_pattern, text, re.MULTILINE | re.DOTALL)
    for match in sects_matches:
        sec_title = match.group(0).split("\n")[0]
        sec_description, sec_content = get_description_and_content(
            match.group(2).strip()
        )
        sec_content = match.group(2).strip()
        section = {
            sections_name: sec_title,
            "description": sec_description,
        }
        if have_content:
            section["content"] = sec_content
        sections.append(section)
    return sections


def get_description_and_content(text: str):
    stop_pattern = r"^(TITULO|ARTICULO|CAPITULO)\b"

    # Search the first occurrence of the stop pattern
    match = re.search(stop_pattern, text, re.MULTILINE)

    if match:
        return (
            text[: match.start()].strip(),
            text.strip(),
        )  # Extract the description before the stop pattern
    return (Full, text.strip())  # If no stop pattern is found, return the whole text


def parse_legal_document(text):
    # Expresiones regulares para identificar secciones
    book_pattern = r"^(LIBRO|LBRO)\s+[^\n]+"
    title_pattern = r"^TITULO\s+[^\n]+"
    chapter_pattern = r"^CAPITULO\s+[^\n]+"
    article_pattern = r"^ARTICULO\s+(\d+-?[A-Z]?)\.\s*(.+)"

    # Estructura principal
    structure = {"title": "", "description": "", "sections": []}
    current_book = None
    current_title = None
    current_chapter = None
    current_article = None

    for line in text.split("\n"):
        line = line.strip()

        # Detectar libros
        book_match = re.match(book_pattern, line)
        if book_match:
            current_book = {
                "title": book_match.group(0),
                "description": "",
                "sections": [],
                "articles": [],
            }
            structure["sections"].append(current_book)
            current_title = None
            current_chapter = None
            current_article = None
            continue

        # Detectar títulos
        title_match = re.match(title_pattern, line)
        if title_match and current_book:
            current_title = {
                "title": title_match.group(0),
                "description": "",
                "sections": [],
                "articles": [],
            }
            current_book["sections"].append(current_title)
            current_chapter = None
            current_article = None
            continue

        # Detectar capítulos
        chapter_match = re.match(chapter_pattern, line)
        if chapter_match and current_title:
            current_chapter = {
                "title": chapter_match.group(0),
                "description": "",
                "articles": [],
            }
            current_title["sections"].append(current_chapter)
            current_article = None
            continue

        # Detectar artículos (con sufijos opcionales)
        article_match = re.match(article_pattern, line)
        if article_match:
            article = {
                "title": f"ARTICULO {article_match.group(1)}",
                "content": article_match.group(
                    2
                ),  # Captura todo el contenido inicial del artículo
            }

            # Si hay un capítulo actual, agregar el artículo dentro de él
            if current_chapter:
                current_chapter["articles"].append(article)
            # Si no hay un capítulo, el artículo pertenece directamente al título
            elif current_title:
                current_title["articles"].append(article)

            current_article = (
                article  # Mantener referencia para agregar contenido adicional
            )
            continue

        # Si encontramos contenido adicional para el artículo actual
        if current_article:
            current_article["content"] += (
                " " + line
            )  # Agregar contenido adicional al artículo
        elif current_chapter:
            current_chapter["description"] += " " + line
        elif current_title:
            current_title["description"] += " " + line
        elif current_book:
            current_book["description"] += " " + line
        else:
            structure["description"] += " " + line

    return structure
