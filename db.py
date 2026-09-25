"""SQLite storage for KEYSTROKE QUEST (standard library only).

Every public function opens a fresh short-lived connection and closes it again,
so Flask's threaded dev server never trips the "SQLite objects created in a
thread can only be used in that same thread" error.  All public functions return
plain dicts / lists of dicts - never ``sqlite3.Row`` - so they stay JSON safe.
"""

import json
import sqlite3

import config
import curriculum
import progress

CACHE_TTL_DAYS = 7
MIN_ATTEMPTS_FOR_WEAK = 5

_SCHEMA = """
CREATE TABLE IF NOT EXISTS player (
    id       INTEGER PRIMARY KEY,
    level    INTEGER NOT NULL DEFAULT 1,
    xp       INTEGER NOT NULL DEFAULT 0,
    settings TEXT    NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_id    INTEGER NOT NULL,
    wpm         REAL    NOT NULL DEFAULT 0,
    raw_wpm     REAL    NOT NULL DEFAULT 0,
    accuracy    REAL    NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    combo_max   INTEGER NOT NULL DEFAULT 0,
    hp_left     INTEGER NOT NULL DEFAULT 0,
    xp          INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stage_progress (
    stage_id      INTEGER PRIMARY KEY,
    passed        INTEGER NOT NULL DEFAULT 0,
    best_wpm      REAL    NOT NULL DEFAULT 0,
    best_accuracy REAL    NOT NULL DEFAULT 0,
    stars         INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS keystats (
    key              TEXT PRIMARY KEY,
    hand             TEXT    NOT NULL DEFAULT 'right',
    finger           TEXT    NOT NULL DEFAULT 'index',
    correct          INTEGER NOT NULL DEFAULT 0,
    miss             INTEGER NOT NULL DEFAULT 0,
    total_latency_ms INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ai_cache (
    key        TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_runs_created ON runs (created_at);
"""


# --------------------------------------------------------------------------
# Connection helpers
# --------------------------------------------------------------------------


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create every table if needed and make sure the single player row exists."""
    conn = get_conn()
    try:
        with conn:
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO player (id, level, xp, settings) VALUES (1, 1, 0, '{}')"
            )
    finally:
        conn.close()


def _rows(sql: str, params=()) -> list[dict]:
    conn = get_conn()
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _row(sql: str, params=()) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Runs and stage progress
# --------------------------------------------------------------------------


def record_run(stage_id, wpm, raw_wpm, accuracy, duration_ms, combo_max, hp_left, xp) -> int:
    conn = get_conn()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO runs (stage_id, wpm, raw_wpm, accuracy, duration_ms,
                                  combo_max, hp_left, xp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(stage_id),
                    float(wpm or 0),
                    float(raw_wpm or 0),
                    float(accuracy or 0),
                    int(duration_ms or 0),
                    int(combo_max or 0),
                    int(hp_left or 0),
                    int(xp or 0),
                ),
            )
            return int(cur.lastrowid)
    finally:
        conn.close()


def mark_passed(stage_id, wpm, accuracy, stars) -> None:
    """Flag the stage as cleared and keep the personal bests."""
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO stage_progress (stage_id, passed, best_wpm, best_accuracy, stars)
                VALUES (?, 1, ?, ?, ?)
                ON CONFLICT(stage_id) DO UPDATE SET
                    passed        = 1,
                    best_wpm      = MAX(best_wpm, excluded.best_wpm),
                    best_accuracy = MAX(best_accuracy, excluded.best_accuracy),
                    stars         = MAX(stars, excluded.stars),
                    updated_at    = CURRENT_TIMESTAMP
                """,
                (int(stage_id), float(wpm or 0), float(accuracy or 0), int(stars or 0)),
            )
    finally:
        conn.close()


def get_progress() -> dict:
    stages = {}
    for row in _rows("SELECT * FROM stage_progress"):
        stages[int(row["stage_id"])] = {
            "passed": bool(row["passed"]),
            "best_wpm": float(row["best_wpm"] or 0),
            "best_accuracy": float(row["best_accuracy"] or 0),
            "stars": int(row["stars"] or 0),
        }

    total = len(curriculum.STAGES)
    highest_passed = max((sid for sid, s in stages.items() if s["passed"]), default=0)
    unlocked_max = max(1, min(total, highest_passed + 1))
    return {"stages": stages, "unlocked_max": unlocked_max}


def get_wpm_history(limit: int = 50) -> list[dict]:
    """Most recent runs, oldest first so a chart reads left to right."""
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 50
    rows = _rows(
        "SELECT created_at, wpm, accuracy FROM runs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows.reverse()
    return [
        {
            "created_at": row["created_at"],
            "wpm": float(row["wpm"] or 0),
            "accuracy": float(row["accuracy"] or 0),
        }
        for row in rows
    ]


# --------------------------------------------------------------------------
# Player
# --------------------------------------------------------------------------


def _parse_settings(blob) -> dict:
    """Corrupt or non-object JSON degrades to an empty dict instead of raising."""
    try:
        settings = json.loads(blob or "{}")
    except (TypeError, ValueError):
        return {}
    return settings if isinstance(settings, dict) else {}


def get_player() -> dict:
    row = _row("SELECT level, xp, settings FROM player WHERE id = 1")
    if row is None:
        init_db()
        row = _row("SELECT level, xp, settings FROM player WHERE id = 1") or {}

    return {
        "level": int(row.get("level") or 1),
        "xp": int(row.get("xp") or 0),
        "settings": _parse_settings(row.get("settings")),
    }


def add_xp(amount: int) -> dict:
    """Award xp and re-derive the level.  Done in one transaction so two
    concurrent requests cannot lose each other's xp."""
    try:
        amount = int(amount or 0)
    except (TypeError, ValueError):
        amount = 0

    conn = get_conn()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE player SET xp = MAX(0, xp + ?) WHERE id = 1", (amount,))
            row = conn.execute("SELECT level, xp, settings FROM player WHERE id = 1").fetchone()
            if row is None:
                return {"level": 1, "xp": 0, "settings": {}}
            total = int(row["xp"] or 0)
            level = progress.level_for_xp(total)["level"]
            conn.execute("UPDATE player SET level = ? WHERE id = 1", (level,))
            settings = _parse_settings(row["settings"])
    finally:
        conn.close()

    return {"level": level, "xp": total, "settings": settings}


def save_settings(settings: dict) -> None:
    """Merge into the stored settings so a partial payload never wipes the rest."""
    merged = get_player()["settings"]
    if isinstance(settings, dict):
        merged.update(settings)

    conn = get_conn()
    try:
        with conn:
            conn.execute("UPDATE player SET settings = ? WHERE id = 1", (json.dumps(merged),))
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Key statistics
# --------------------------------------------------------------------------


def upsert_keystats(keystrokes: list[dict]) -> None:
    """Fold a run's keystrokes into the per-key totals."""
    if not keystrokes:
        return

    tally: dict[str, dict] = {}
    for stroke in keystrokes:
        if not isinstance(stroke, dict):
            continue
        expected = stroke.get("expected")
        if not isinstance(expected, str) or expected == "":
            continue

        typed = stroke.get("typed")
        ok = isinstance(typed, str) and typed == expected
        try:
            ms = max(0, int(float(stroke.get("ms") or 0)))
        except (TypeError, ValueError):
            ms = 0

        entry = tally.setdefault(expected, {"correct": 0, "miss": 0, "ms": 0})
        if ok:
            entry["correct"] += 1
            entry["ms"] += ms
        else:
            entry["miss"] += 1

    if not tally:
        return

    payload = []
    for key, entry in tally.items():
        finger = curriculum.finger_for(key)
        payload.append(
            (
                key,
                finger.get("hand", "right"),
                finger.get("finger", "index"),
                entry["correct"],
                entry["miss"],
                entry["ms"],
            )
        )

    conn = get_conn()
    try:
        with conn:
            conn.executemany(
                """
                INSERT INTO keystats (key, hand, finger, correct, miss, total_latency_ms)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    hand             = excluded.hand,
                    finger           = excluded.finger,
                    correct          = correct + excluded.correct,
                    miss             = miss + excluded.miss,
                    total_latency_ms = total_latency_ms + excluded.total_latency_ms
                """,
                payload,
            )
    finally:
        conn.close()


def _keystat_dict(row: dict) -> dict:
    correct = int(row["correct"] or 0)
    miss = int(row["miss"] or 0)
    attempts = correct + miss
    latency = int(row["total_latency_ms"] or 0)
    return {
        "key": row["key"],
        "accuracy": round(correct / attempts, 4) if attempts else 0.0,
        "finger": row["finger"] or "index",
        "hand": row["hand"] or "right",
        "avg_ms": int(round(latency / correct)) if correct else 0,
        "attempts": attempts,
        "correct": correct,
        "miss": miss,
    }


def get_weak_keys(limit: int = 5) -> list[dict]:
    """Worst keys first: lowest accuracy, then slowest.  Space is never listed."""
    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        limit = 5
    if limit == 0:
        return []

    rows = [
        _keystat_dict(row)
        for row in _rows("SELECT * FROM keystats WHERE key != ' '")
    ]
    rows = [row for row in rows if row["attempts"] >= MIN_ATTEMPTS_FOR_WEAK]
    rows.sort(key=lambda r: (r["accuracy"], -r["avg_ms"]))
    return rows[:limit]


def get_key_heatmap() -> list[dict]:
    rows = [_keystat_dict(row) for row in _rows("SELECT * FROM keystats")]
    rows.sort(key=lambda r: r["key"])
    return rows


# --------------------------------------------------------------------------
# AI response cache
# --------------------------------------------------------------------------


def cache_get(key: str) -> dict | None:
    if not key:
        return None
    row = _row(
        f"""
        SELECT payload FROM ai_cache
        WHERE key = ? AND created_at >= datetime('now', '-{CACHE_TTL_DAYS} days')
        """,
        (str(key),),
    )
    if not row:
        return None
    try:
        payload = json.loads(row["payload"])
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def cache_set(key: str, payload: dict) -> None:
    if not key:
        return
    try:
        blob = json.dumps(payload)
    except (TypeError, ValueError):
        return

    conn = get_conn()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO ai_cache (key, payload, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    payload    = excluded.payload,
                    created_at = CURRENT_TIMESTAMP
                """,
                (str(key), blob),
            )
    finally:
        conn.close()
