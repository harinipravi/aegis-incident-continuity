"""
SQLite persistence for Aegis incident decisions and RCA results.
"""

import json
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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS rca_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            service_name TEXT NOT NULL,
            suspected_root_cause TEXT NOT NULL,
            evidence_summary TEXT NOT NULL,
            recommended_mitigation TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            result_json TEXT NOT NULL,
            generated_at TEXT NOT NULL
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


def save_rca_result(incident_id: str, result: dict) -> dict:
    """Persist a completed RCA result to the rca_results table."""
    generated_at = datetime.now(timezone.utc).isoformat()

    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO rca_results
        (incident_id, service_name, suspected_root_cause, evidence_summary,
         recommended_mitigation, confidence_score, result_json, generated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            result.get("service_name", ""),
            result.get("suspected_root_cause", ""),
            result.get("evidence_summary", ""),
            result.get("recommended_mitigation", ""),
            result.get("confidence_score", 0.0),
            json.dumps(result),
            generated_at,
        ),
    )

    conn.commit()
    row_id = cursor.lastrowid
    conn.close()

    return {"id": row_id, "incident_id": incident_id, "generated_at": generated_at}


def list_rca_results(limit: int = 20) -> list:
    """Return the most recent RCA results across all incidents."""
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT id, incident_id, service_name, suspected_root_cause,
               confidence_score, generated_at
        FROM rca_results
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]
