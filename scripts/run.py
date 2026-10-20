import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def index_ready() -> bool:
    from pr_triage.rag.index import get_collection

    return get_collection().count() > 0


def main() -> None:
    os.chdir(ROOT)
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("Falta a OPENAI_API_KEY. Copia .env.example para .env e preenche a chave.")

    if "--rebuild" in sys.argv or not index_ready():
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_index.py")],
            cwd=ROOT,
            check=True,
        )
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "streamlit_app.py")],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()