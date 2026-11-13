"""No-hardware orchestration of ScanPick/ScanPlace over an injected stage adapter.

This separates task sequencing from JAKA/planning. The adapter is deliberately
not auto-created: production must supply the existing canonical owner/services.
"""
import json
import math
import sqlite3
import time
import uuid
from .contracts import PICK, PLACE

class BlockFault(RuntimeError):
    pass

class PayloadSessions:
    def __init__(self, path):
        self.db=sqlite3.connect(str(path))
        self.db.execute('CREATE TABLE IF NOT EXISTS payloads (id TEXT PRIMARY KEY, object_type TEXT, tool_revision TEXT, geometry_revision TEXT, evidence TEXT, state TEXT)')
        self.db.commit()
    def create(self, object_type, tool_revision, geometry_revision, evidence, *, state="HELD_CONFIRMED"):
        if not all((object_type, tool_revision, geometry_revision, evidence)):
            raise BlockFault('PAYLOAD_BINDING_INCOMPLETE')
        if state not in ('HELD_CONFIRMED', 'PICK_IN_PROGRESS'):
            raise BlockFault('INVALID_INITIAL_PAYLOAD_STATE')
        sid=uuid.uuid4().hex
        with self.db:self.db.execute('INSERT INTO payloads VALUES (?,?,?,?,?,?)',
             (sid,object_type,tool_revision,geometry_revision,json.dumps(evidence),state))
        return sid
    def active(self):
        return self.db.execute("SELECT id,state FROM payloads WHERE state IN ('HELD_CONFIRMED','PICK_IN_PROGRESS','UNCERTAIN')").fetchall()
    def confirm_pick(self, sid, evidence):
        with self.db:
            cur=self.db.execute("UPDATE payloads SET state='HELD_CONFIRMED', evidence=? WHERE id=? AND state='PICK_IN_PROGRESS'",
                                (json.dumps(evidence),sid))
            if cur.rowcount!=1:raise BlockFault('PAYLOAD_STATE_CONFLICT')
    def get(self, sid):
        row=self.db.execute('SELECT object_type,tool_revision,geometry_revision,evidence,state FROM payloads WHERE id=?',(sid,)).fetchone()
        if not row:raise BlockFault('PAYLOAD_SESSION_UNKNOWN')
        return dict(object_type=row[0],tool_revision=row[1],geometry_revision=row[2],evidence=json.loads(row[3]),state=row[4])
    def transition(self, sid, expected, state):
        with self.db:
            cur=self.db.execute('UPDATE payloads SET state=? WHERE id=? AND state=?',(state,sid,expected))
            if cur.rowcount!=1:raise BlockFault('PAYLOAD_STATE_CONFLICT')
    def close(self):self.db.close()

class BlockRunner:
    def __init__(self, adapter, sessions, *, clock=time.monotonic, event=lambda row:None):
        self.adapter=adapter;self.sessions=sessions;self.clock=clock;self.event=event
    def stop_confirmed(self):
        try:return self.adapter.stop() is True
        except Exception:return False
    def run(self, plan, *, payload_session_id='', cancelled=lambda:False):
        # Even injected test adapters cannot silently open an execution route.
        if getattr(self.adapter,'mode',None)!='OFFLINE':
            raise BlockFault('PRODUCTION_ADAPTER_NOT_RELEASED')
        kind='pick' if plan['stages']==list(PICK) else 'place'
        expected=list(PICK) if kind=='pick' else list(PLACE)
        if kind=='place' and plan['stages'][-1:] == ['CENTER']:expected+=['CENTER']
        if plan['stages']!=expected:raise BlockFault('INVALID_STAGE_SEQUENCE')
        sid=payload_session_id;payload=None;started=self.clock();events=[]
        if kind=='place':
            payload=self.sessions.get(sid)
            if payload['state']!='HELD_CONFIRMED':raise BlockFault('PAYLOAD_NOT_HELD')
        released=False
        try:
            for stage in plan['stages']:
                if cancelled():
                    stopped=self.stop_confirmed()
                    if sid and not released:
                        self.sessions.transition(sid,'HELD_CONFIRMED','UNCERTAIN')
                    return dict(success=False,terminal_state='STOPPED' if stopped else 'UNCERTAIN',
                                payload_session_id=sid,events=events,physical_motion=False)
                if stage=='HOLD_CONFIRMED':
                    proof=events[-1]['evidence']
                    sid=self.sessions.create(proof.get('object_type'),proof.get('tool_revision'),
                                             proof.get('geometry_revision'),proof)
                    evidence=dict(verified=True,payload_session_id=sid)
                else:
                    evidence=self.adapter.stage(stage, payload=payload)
                    observed=evidence.get('observed_monotonic_s')
                    now=self.clock()
                    if not isinstance(observed,(int,float)) or not math.isfinite(observed) or not 0<=now-observed<=2:
                        raise BlockFault('STALE_STAGE_EVIDENCE:'+stage)
                    if evidence.get('verified') is not True:raise BlockFault('UNVERIFIED_STAGE:'+stage)
                    if stage=='VERIFY_PAYLOAD':
                        if any(evidence.get(k)!=payload[k] for k in ('object_type','tool_revision','geometry_revision')):
                            raise BlockFault('PAYLOAD_BINDING_CHANGED')
                    if stage=='RELEASE_CONFIRMED':
                        self.sessions.transition(sid,'HELD_CONFIRMED','RELEASED_CONFIRMED');released=True
                row=dict(stage=stage,state='VERIFIED',elapsed_s=self.clock()-started,evidence=evidence)
                events.append(row);self.event(row)
            return dict(success=True,terminal_state='HELD_CONFIRMED' if kind=='pick' else 'RELEASED_RETREATED',
                        payload_session_id=sid,payload_state=self.sessions.get(sid)['state'],
                        transport_handoff_ready=False,physical_motion=False,events=events)
        except Exception as exc:
            stopped=self.stop_confirmed()
            if sid and not released and self.sessions.get(sid)['state']=='HELD_CONFIRMED':
                self.sessions.transition(sid,'HELD_CONFIRMED','UNCERTAIN')
            return dict(success=False,terminal_state='FAULT' if stopped else 'UNCERTAIN',
                        code=str(exc),payload_session_id=sid,
                        payload_state=self.sessions.get(sid)['state'] if sid else 'UNKNOWN',
                        events=events,physical_motion=False)
