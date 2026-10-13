import re
from pathlib import Path

from pydantic import BaseModel

POLICIES_DIR = Path("data/policies")
DATE_PREFIX = "Data de entrada em vigor:"
CLAUSE_PATTERN = re.compile(r"^## (\d+\.\d+) (.+)$")


class Chunk(BaseModel):
    chunk_id: str
    source: str
    document: str
    clause: str
    title: str
    effective_date: str | None
    text: str


def chunk_document(path: Path) -> list[Chunk]:
    document = ""
    effective_date = None
    clauses: list[tuple[str, str, list[str]]] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        match = CLAUSE_PATTERN.match(line)
        if line.startswith("# "):
            document = line[2:].split("—", 1)[-1].strip()
        elif match:
            clauses.append((match.group(1), match.group(2), []))
        elif clauses:
            clauses[-1][2].append(line)
        elif line.startswith(DATE_PREFIX):
            effective_date = line.removeprefix(DATE_PREFIX).strip()

    chunks = []
    for clause, title, body_lines in clauses:
        body = "\n".join(body_lines).strip()
        header = f"Documento: {document} | Cláusula {clause} | {title}"
        chunks.append(
            Chunk(
                chunk_id=f"{path.stem}#{clause}",
                source=path.name,
                document=document,
                clause=clause,
                title=title,
                effective_date=effective_date,
                text=f"{header}\n{body}",
            )
        )
    return chunks


def load_chunks(directory: Path = POLICIES_DIR) -> list[Chunk]:
    chunks = []
    for path in sorted(directory.glob("*.md")):
        chunks.extend(chunk_document(path))
    return chunks