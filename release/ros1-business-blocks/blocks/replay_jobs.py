"""Durable OFFLINE replay job semantics; not a physical job owner.

SQLite atomic request reservation models lost ACK/restart behavior for a future
canonical adapter. No retry of a physical command is implemented here.
"""
import hashlib
import json
import sqlite3
import uuid

class ReplayJobs:
    def __init__(self, path):
        self.db=sqlite3.connect(str(path))
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (request TEXT PRIMARY KEY, fingerprint TEXT, run_id TEXT UNIQUE, state TEXT)')
        self.db.commit()
    def start(self, goal):
        if not goal.get('request_id'):
            raise ValueError('REQUEST_ID_REQUIRED')
        fingerprint=hashlib.sha256(json.dumps(goal,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old=self.db.execute('SELECT fingerprint, run_id, state FROM jobs WHERE request=?',(goal['request_id'],)).fetchone()
            if old:
                if old[0]!=fingerprint:raise ValueError('REQUEST_ID_CONFLICT')
                self.db.commit();return dict(run_id=old[1],state=old[2],new_job=False)
            busy=self.db.execute("SELECT run_id FROM jobs WHERE state IN ('RUNNING','STOPPING','UNCERTAIN')").fetchone()
            if busy:raise ValueError('BUSY_OR_RECOVERY_REQUIRED')
            run=uuid.uuid4().hex
            self.db.execute('INSERT INTO jobs VALUES (?,?,?,?)',(goal['request_id'],fingerprint,run,'RUNNING'))
            self.db.commit();return dict(run_id=run,state='RUNNING',new_job=True)
        except BaseException:
            self.db.rollback();raise
    def finish(self, run_id, state):
        if state not in ('SUCCEEDED','FAULT','UNCERTAIN'):
            raise ValueError('INVALID_TERMINAL_STATE')
        with self.db:
            row=self.db.execute('SELECT state FROM jobs WHERE run_id=?',(run_id,)).fetchone()
            if not row or row[0]!='RUNNING':raise ValueError('JOB_NOT_RUNNING')
            self.db.execute('UPDATE jobs SET state=? WHERE run_id=?',(state,run_id))
    def cancel(self, run_id, *, stop_confirmed=False):
        with self.db:
            row=self.db.execute('SELECT state FROM jobs WHERE run_id=?',(run_id,)).fetchone()
            if not row or row[0] not in ('RUNNING','STOPPING'):
                raise ValueError('JOB_NOT_ACTIVE')
            state='STOPPED' if stop_confirmed else 'STOPPING'
            self.db.execute('UPDATE jobs SET state=? WHERE run_id=?',(state,run_id))
        return state
    def close(self):self.db.close()
