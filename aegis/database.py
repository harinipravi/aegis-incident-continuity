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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS incident_states (
            incident_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'INVESTIGATING',
            resolved_at TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS runbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            service_name TEXT NOT NULL,
            title TEXT NOT NULL,
            root_cause TEXT NOT NULL,
            mitigation TEXT NOT NULL,
            evidence_summary TEXT NOT NULL,
            created_at TEXT NOT NULL
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

def set_incident_status(
    incident_id: str,
    status: str,
    resolved_at: str | None = None
):
    if status not in {"INVESTIGATING", "MITIGATION APPROVED", "RESOLVED"}:
        raise ValueError("Invalid incident status")

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO incident_states (incident_id, status, resolved_at)
        VALUES (?, ?, ?)
        ON CONFLICT(incident_id) DO UPDATE SET
            status = excluded.status,
            resolved_at = excluded.resolved_at
        """,
        (incident_id, status, resolved_at),
    )

    conn.commit()
    conn.close()

    return {
        "incident_id": incident_id,
        "status": status,
        "resolved_at": resolved_at,
    }


def get_incident_status(incident_id: str):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT incident_id, status, resolved_at
        FROM incident_states
        WHERE incident_id = ?
        """,
        (incident_id,),
    ).fetchone()

    # If the incident has already been resolved, return the persisted state.
    if row is not None and row["status"] == "RESOLVED":
        conn.close()
        return dict(row)

    # Preserve compatibility with mitigation approvals recorded before
    # incident_states was introduced.
    decision_row = conn.execute(
        """
        SELECT decision
        FROM mitigation_decisions
        WHERE incident_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (incident_id,),
    ).fetchone()

    conn.close()

    if decision_row is not None and decision_row["decision"] == "APPROVED":
        return {
            "incident_id": incident_id,
            "status": "MITIGATION APPROVED",
            "resolved_at": None,
        }

    if row is None:
        return {
            "incident_id": incident_id,
            "status": "INVESTIGATING",
            "resolved_at": None,
        }

    return dict(row)


def save_runbook(
    incident_id: str,
    service_name: str,
    title: str,
    root_cause: str,
    mitigation: str,
    evidence_summary: str,
):
    conn = get_connection()

    # Keep one runbook per incident.
    existing = conn.execute(
        """
        SELECT *
        FROM runbooks
        WHERE incident_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (incident_id,),
    ).fetchone()

    if existing is not None:
        conn.close()
        return dict(existing)

    created_at = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        """
        INSERT INTO runbooks (
            incident_id,
            service_name,
            title,
            root_cause,
            mitigation,
            evidence_summary,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            service_name,
            title,
            root_cause,
            mitigation,
            evidence_summary,
            created_at,
        ),
    )

    conn.commit()

    row = conn.execute(
        "SELECT * FROM runbooks WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()

    conn.close()
    return dict(row)



def list_runbooks(limit: int = 50):
    conn = get_connection()

    # Return only the latest runbook for each incident,
    # together with the current incident lifecycle state.
    rows = conn.execute(
        """
        SELECT
            r.*,
            COALESCE(
                ist.status,
                CASE
                    WHEN md.decision = 'APPROVED'
                    THEN 'MITIGATION APPROVED'
                    ELSE 'INVESTIGATING'
                END
            ) AS incident_status,
            ist.resolved_at
        FROM runbooks r
        INNER JOIN (
            SELECT incident_id, MAX(id) AS latest_id
            FROM runbooks
            GROUP BY incident_id
        ) latest
            ON r.incident_id = latest.incident_id
            AND r.id = latest.latest_id
        LEFT JOIN incident_states ist
            ON r.incident_id = ist.incident_id
        LEFT JOIN (
            SELECT incident_id, decision
            FROM mitigation_decisions md1
            WHERE id = (
                SELECT MAX(id)
                FROM mitigation_decisions md2
                WHERE md2.incident_id = md1.incident_id
            )
        ) md
            ON r.incident_id = md.incident_id
        ORDER BY r.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    conn.close()
    return [dict(row) for row in rows]
