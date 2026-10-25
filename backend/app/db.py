"""SQLite storage for profiles, opportunities, analyses, traces and the response cache."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from .config import settings

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    website TEXT,
    data TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    data TEXT NOT NULL,
    first_seen REAL NOT NULL,
    UNIQUE(profile_id, url)
);
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    label TEXT,
    data TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS watch_runs (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    new_count INTEGER NOT NULL,
    data TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = sqlite3.connect(settings.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


# --- cache -----------------------------------------------------------------

def cache_get(key: str) -> Any | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else None


def cache_put(key: str, value: Any) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, created_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time()),
        )


# --- profiles --------------------------------------------------------------

def save_profile(profile: dict, profile_id: str | None = None) -> str:
    pid = profile_id or profile.get("id") or new_id()
    profile["id"] = pid
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO profiles (id, name, website, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (pid, profile.get("name", ""), profile.get("website", ""), json.dumps(profile), time.time()),
        )
    return pid


def get_profile(profile_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT data FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def list_profiles() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT data FROM profiles ORDER BY created_at DESC").fetchall()
    return [json.loads(r["data"]) for r in rows]


# --- opportunities ---------------------------------------------------------

def upsert_opportunity(profile_id: str, opp: dict) -> tuple[str, bool]:
    """Store an opportunity; returns (id, is_new)."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM opportunities WHERE profile_id = ? AND url = ?", (profile_id, opp["url"])
        ).fetchone()
        if row:
            opp["id"] = row["id"]
            conn.execute(
                "UPDATE opportunities SET title = ?, data = ? WHERE id = ?",
                (opp.get("title"), json.dumps(opp), row["id"]),
            )
            return row["id"], False
        oid = opp.get("id") or new_id()
        opp["id"] = oid
        conn.execute(
            "INSERT INTO opportunities (id, profile_id, url, title, data, first_seen) VALUES (?, ?, ?, ?, ?, ?)",
            (oid, profile_id, opp["url"], opp.get("title"), json.dumps(opp), time.time()),
        )
        return oid, True


def get_opportunity(opp_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT data, first_seen FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
    if not row:
        return None
    opp = json.loads(row["data"])
    opp["first_seen"] = row["first_seen"]
    return opp


def list_opportunities(profile_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT data, first_seen FROM opportunities WHERE profile_id = ? ORDER BY first_seen DESC",
            (profile_id,),
        ).fetchall()
    out = []
    for r in rows:
        opp = json.loads(r["data"])
        opp["first_seen"] = r["first_seen"]
        out.append(opp)
    return out


# --- analyses --------------------------------------------------------------

def save_analysis(opportunity_id: str, kind: str, data: dict) -> str:
    aid = new_id()
    with connect() as conn:
        conn.execute(
            "INSERT INTO analyses (id, opportunity_id, kind, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (aid, opportunity_id, kind, json.dumps(data), time.time()),
        )
    return aid


def latest_analysis(opportunity_id: str, kind: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM analyses WHERE opportunity_id = ? AND kind = ? ORDER BY created_at DESC LIMIT 1",
            (opportunity_id, kind),
        ).fetchone()
    return json.loads(row["data"]) if row else None


# --- traces ----------------------------------------------------------------

def save_trace(trace_id: str, label: str, data: dict) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO traces (id, label, data, created_at) VALUES (?, ?, ?, ?)",
            (trace_id, label, json.dumps(data), time.time()),
        )


def list_traces(limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT data FROM traces ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [json.loads(r["data"]) for r in rows]


# --- watch runs ------------------------------------------------------------

def save_watch_run(profile_id: str, new_items: list[dict]) -> str:
    wid = new_id()
    with connect() as conn:
        conn.execute(
            "INSERT INTO watch_runs (id, profile_id, new_count, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (wid, profile_id, len(new_items), json.dumps(new_items), time.time()),
        )
    return wid


def list_watch_runs(profile_id: str, limit: int = 20) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, new_count, data, created_at FROM watch_runs WHERE profile_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (profile_id, limit),
        ).fetchall()
    return [
        {"id": r["id"], "new_count": r["new_count"], "items": json.loads(r["data"]), "created_at": r["created_at"]}
        for r in rows
    ]
