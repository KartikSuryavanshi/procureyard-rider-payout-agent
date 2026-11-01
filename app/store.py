import csv, json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .models import PendingItem, TraceStep

class Store:
    def __init__(self, data_dir: Path, db_path: Path):
        self.data_dir = data_dir
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""CREATE TABLE IF NOT EXISTS messages(message_id TEXT PRIMARY KEY, rider_id TEXT, reply TEXT);
        CREATE TABLE IF NOT EXISTS traces(id INTEGER PRIMARY KEY, rider_id TEXT, at TEXT, type TEXT, name TEXT, input TEXT, output TEXT);
        CREATE TABLE IF NOT EXISTS pending(id TEXT PRIMARY KEY, rider_id TEXT, type TEXT, amount INTEGER, reason TEXT, created_at TEXT, status TEXT DEFAULT 'pending');""")
        self.db.commit()
        self.riders = list(csv.DictReader(open(data_dir/'riders.csv')))
        self.trips = list(csv.DictReader(open(data_dir/'trips.csv')))
        self.lines = list(csv.DictReader(open(data_dir/'payout_lines.csv')))
        self.riders_by_id = {r['rider_id']: r for r in self.riders}
        self.trips_by_id = {t['trip_id']: t for t in self.trips}

    def normalize_rider(self, rider_id: str) -> str:
        if rider_id == 'R7': return 'R007'
        return rider_id

    def trip_rows(self, rider_id: str, dates: list[str] | None = None, trip_ids: list[str] | None = None):
        rid = self.normalize_rider(rider_id)
        rows = [t for t in self.trips if self.normalize_rider(t['rider_id']) == rid]
        if trip_ids: rows = [t for t in rows if t['trip_id'] in trip_ids]
        if dates:
            ds = {f'2026-09-{int(d):02d}' for d in dates}
            rows = [t for t in rows if t['started_at'][:10] in ds]
        return rows

    def payout_lines(self, rider_id: str, trip_id: str | None = None, date: str | None = None):
        rid = self.normalize_rider(rider_id)
        return [x for x in self.lines if self.normalize_rider(x['rider_id']) == rid and (trip_id is None or x['trip_id']==trip_id) and (date is None or x['payout_date']==date)]

    def trace(self, rider_id: str, typ: str, name: str, inp: Any, out: Any):
        now=datetime.now(timezone.utc).isoformat()
        self.db.execute('INSERT INTO traces(rider_id,at,type,name,input,output) VALUES(?,?,?,?,?,?)', (rider_id,now,typ,name,json.dumps(inp, default=str),json.dumps(out, default=str)))
        self.db.commit()

    def get_trace(self, rider_id: str):
        out=[]
        for r in self.db.execute('SELECT at,type,name,input,output FROM traces WHERE rider_id=? ORDER BY id',(rider_id,)):
            out.append({'at':r['at'],'type':r['type'],'name':r['name'],'input':json.loads(r['input']) if r['input'] else None,'output':json.loads(r['output']) if r['output'] else None})
        return out

    def prior_messages(self, rider_id: str):
        rows=self.db.execute("SELECT input FROM traces WHERE rider_id=? AND type='message_in' ORDER BY id",(rider_id,))
        return [json.loads(x['input']).get('text','') for x in rows]

    def duplicate(self, message_id: str): return self.db.execute('SELECT reply FROM messages WHERE message_id=?',(message_id,)).fetchone()
    def save_message(self, message_id: str, rider_id: str, reply: str):
        self.db.execute('INSERT OR REPLACE INTO messages VALUES(?,?,?)',(message_id,rider_id,reply)); self.db.commit()
    def add_pending(self, item: PendingItem):
        self.db.execute('INSERT OR IGNORE INTO pending VALUES(?,?,?,?,?,?,?)',(item.id,item.rider_id,item.type,item.amount,item.reason,item.created_at,'pending')); self.db.commit()
    def pending(self):
        return [dict(x) for x in self.db.execute("SELECT id,rider_id,type,amount,reason,created_at FROM pending WHERE status='pending' ORDER BY created_at")]

    def decide_pending(self, item_id: str, decision: str):
        if decision not in {'approved','rejected'}: return False
        cur=self.db.execute("UPDATE pending SET status=? WHERE id=? AND status='pending'",(decision,item_id)); self.db.commit(); return cur.rowcount == 1
