"""Local SQLite snapshots, normalized transcripts and computed reports; no tokens."""
import json
from pathlib import Path
import sqlite3
from .common import AuditorError


class Store:
    def __init__(self, path="runtime/auditor.sqlite3"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS snapshots(source TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS transcripts(source TEXT, id TEXT, payload TEXT NOT NULL,
                    PRIMARY KEY(source,id));
                CREATE TABLE IF NOT EXISTS reports(source TEXT, days INTEGER, payload TEXT NOT NULL,
                    PRIMARY KEY(source,days));
            """)

    def connect(self):
        return sqlite3.connect(self.path)

    def save_snapshot(self, source, snapshot):
        metadata = dict(snapshot)
        calls = metadata.pop("calls", [])
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO snapshots VALUES (?,?)", (source, json.dumps(metadata, ensure_ascii=False)))
            db.execute("DELETE FROM transcripts WHERE source=?", (source,))
            db.executemany("INSERT INTO transcripts VALUES (?,?,?)", [(source, str(call["id"]), json.dumps(call, ensure_ascii=False)) for call in calls])
            db.execute("DELETE FROM reports WHERE source=?", (source,))

    def snapshot(self, source):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM snapshots WHERE source=?", (source,)).fetchone()
            if row is None:
                raise AuditorError("No live snapshot. Run sync-amo first.")
            result = json.loads(row[0])
            result["calls"] = [json.loads(item[0]) for item in db.execute("SELECT payload FROM transcripts WHERE source=? ORDER BY id", (source,))]
            return result

    def save_report(self, source, days, report):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO reports VALUES (?,?,?)", (source, days, json.dumps(report, ensure_ascii=False)))
