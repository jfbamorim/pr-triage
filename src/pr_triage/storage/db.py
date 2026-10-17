import sqlite3
from datetime import datetime, timezone

from pr_triage.workflow import WorkflowResult

DB_PATH = "pr_triage.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fields(result: WorkflowResult) -> tuple:
    pr = result.request
    return (
        pr.item if pr else None,
        pr.quantity if pr else None,
        pr.estimated_value_eur if pr else None,
        pr.cost_center if pr else None,
        pr.category.value if pr else None,
        int(pr.is_urgent) if pr else 0,
        int(pr.mentions_framework_contract) if pr else 0,
        result.status.value,
        result.reason.value if result.reason else None,
        result.band.value if result.band else None,
    )


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT,
                quantity INTEGER,
                estimated_value_eur REAL,
                cost_center TEXT,
                category TEXT,
                is_urgent INTEGER NOT NULL DEFAULT 0,
                mentions_framework_contract INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                reason TEXT,
                band TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def create_request(result: WorkflowResult) -> int:
    now = _now()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO purchase_requests
                (item, quantity, estimated_value_eur, cost_center,
                 category, is_urgent, mentions_framework_contract,
                 status, reason, band, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*_fields(result), now, now),
        )
        return cursor.lastrowid


def update_request(request_id: int, result: WorkflowResult) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE purchase_requests
            SET item = ?, quantity = ?, estimated_value_eur = ?, cost_center = ?,
                category = ?, is_urgent = ?, mentions_framework_contract = ?,
                status = ?, reason = ?, band = ?, updated_at = ?
            WHERE id = ?
            """,
            (*_fields(result), _now(), request_id),
        )


def get_request(request_id: int) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM purchase_requests WHERE id = ?", (request_id,)
        ).fetchone()