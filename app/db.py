"""SQLite persistence — stdlib sqlite3, single file, no ORM, no migrations.

Stores profiles, opportunities, matches, and drafts (PRD section 8). We store the
rich Pydantic models as JSON in a payload column alongside a few indexed scalar
columns — real relational queries, zero setup. The schema creates idempotently.

ponytail: JSON-payload-per-row instead of fully normalized columns. The query
needs here (insert + read back, list by run) don't justify a wide normalized
schema; the JSON column keeps the model the single source of truth.
"""

from __future__ import annotations

import json
import sqlite3
from typing import List, Optional

from app.models import Draft, Match, Opportunity, Profile

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    payload     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS opportunities (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    payload     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id      INTEGER NOT NULL,
    opportunity_id  TEXT NOT NULL,
    fit_score       REAL NOT NULL,
    payload         TEXT NOT NULL,
    FOREIGN KEY (profile_id) REFERENCES profiles(id)
);

CREATE TABLE IF NOT EXISTS drafts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id      INTEGER NOT NULL,
    opportunity_id  TEXT NOT NULL,
    status          TEXT NOT NULL,
    payload         TEXT NOT NULL,
    FOREIGN KEY (profile_id) REFERENCES profiles(id)
);
"""


class Database:
    def __init__(self, path: str = "grant_navigator.db") -> None:
        # check_same_thread=False so the FastAPI app can share a connection;
        # access is serialized in this single-process v1.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self.init_schema()

    def init_schema(self) -> None:
        """Idempotent — safe to call repeatedly."""
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ----------------------------- profiles ---------------------------- #
    def insert_profile(self, profile: Profile) -> int:
        cur = self._conn.execute(
            "INSERT INTO profiles (payload) VALUES (?)",
            (profile.model_dump_json(),),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def get_profile(self, profile_id: int) -> Optional[Profile]:
        row = self._conn.execute(
            "SELECT payload FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        return Profile.model_validate_json(row["payload"]) if row else None

    # --------------------------- opportunities ------------------------- #
    def upsert_opportunity(self, opp: Opportunity) -> None:
        self._conn.execute(
            """
            INSERT INTO opportunities (id, source, title, payload)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                source = excluded.source,
                title  = excluded.title,
                payload = excluded.payload
            """,
            (opp.id, opp.source.value, opp.title, opp.model_dump_json()),
        )
        self._conn.commit()

    def get_opportunity(self, opportunity_id: str) -> Optional[Opportunity]:
        row = self._conn.execute(
            "SELECT payload FROM opportunities WHERE id = ?", (opportunity_id,)
        ).fetchone()
        return Opportunity.model_validate_json(row["payload"]) if row else None

    # ------------------------------ matches ---------------------------- #
    def insert_match(self, profile_id: int, match: Match) -> int:
        cur = self._conn.execute(
            "INSERT INTO matches (profile_id, opportunity_id, fit_score, payload) VALUES (?, ?, ?, ?)",
            (profile_id, match.opportunity_id, match.fit_score, match.model_dump_json()),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def get_matches_for_profile(self, profile_id: int) -> List[Match]:
        rows = self._conn.execute(
            "SELECT payload FROM matches WHERE profile_id = ? ORDER BY fit_score DESC",
            (profile_id,),
        ).fetchall()
        return [Match.model_validate_json(r["payload"]) for r in rows]

    # ------------------------------ drafts ----------------------------- #
    def insert_draft(self, profile_id: int, draft: Draft) -> int:
        cur = self._conn.execute(
            "INSERT INTO drafts (profile_id, opportunity_id, status, payload) VALUES (?, ?, ?, ?)",
            (profile_id, draft.opportunity_id, draft.status.value, draft.model_dump_json()),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def get_drafts_for_profile(self, profile_id: int) -> List[Draft]:
        rows = self._conn.execute(
            "SELECT payload FROM drafts WHERE profile_id = ?", (profile_id,)
        ).fetchall()
        return [Draft.model_validate_json(r["payload"]) for r in rows]
