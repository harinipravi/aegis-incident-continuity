"""
SQLite persistence for Aegis incident decisions.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("aegis.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS mitigation_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            decided_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def record_decision(incident_id: str, decision: str):
    if decision not in {"APPROVED", "REJECTED"}:
        raise ValueError("Invalid mitigation decision")

    decided_at = datetime.now(timezone.utc).isoformat()

    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO mitigation_decisions
        (incident_id, decision, decided_at)
        VALUES (?, ?, ?)
        """,
        (incident_id, decision, decided_at),
    )

    conn.commit()

    decision_id = cursor.lastrowid

    conn.close()

    return {
        "id": decision_id,
        "incident_id": incident_id,
        "decision": decision,
        "decided_at": decided_at,
    }


def get_latest_decision(incident_id: str):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT id, incident_id, decision, decided_at
        FROM mitigation_decisions
        WHERE incident_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (incident_id,),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return dict(row)
