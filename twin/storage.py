"""Explicit snapshot storage. Connections are short-lived and writes atomic."""
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

class ExperimentStore:
    def __init__(self, path='data/experiments.db'):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, name TEXT, created TEXT, payload TEXT)')

    def connect(self): return sqlite3.connect(self.path, timeout=15)

    def save(self, name, plant):
        identity = uuid4().hex
        payload = json.dumps({'rows':plant.rows,'events':plant.events,'config_changes':plant.config_changes})
        with self.connect() as db:
            db.execute('INSERT INTO experiments VALUES (?,?,?,?)',
                       (identity,name.strip() or 'Untitled experiment',datetime.now(timezone.utc).isoformat(),payload))
        return identity

    def list(self):
        with self.connect() as db:
            return [dict(zip(['id','name','created'],row)) for row in db.execute('SELECT id,name,created FROM experiments ORDER BY created DESC')]

    def load(self, identity):
        with self.connect() as db:
            row=db.execute('SELECT payload FROM experiments WHERE id=?',(identity,)).fetchone()
        if row is None: raise KeyError(identity)
        return json.loads(row[0])
