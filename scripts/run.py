import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "data" / "chroma"


def main() -> None:
    rebuild = "--rebuild" in sys.argv
    if rebuild or not INDEX_DIR.exists():
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