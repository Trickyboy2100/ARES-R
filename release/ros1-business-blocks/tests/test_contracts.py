import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT))
from blocks.contracts import registry,prepare,replay,PICK

class Contracts(unittest.TestCase):
    def plan(self,kind='pick',center=False):
        row=next(r for r in registry() if r['kind']==kind and r.get('profile_source'))
        return prepare(row['block_id'],row['profile_revision'],REPO,return_center=center)
    def evidence(self,plan):
        return [dict(stage=s,verified=True,payload_session_id='synthetic-session') for s in plan['stages']]
    def test_inventory(self):
        rows=registry();self.assertEqual(len(rows),11)
        self.assertEqual(sum(r['optional'] for r in rows),2)
        self.assertTrue(all(not r['physical_start_enabled'] for r in rows))
    def test_all_five_profiles_hash_checked(self):
        for row in registry():
            if row.get('profile_source'):
                p=prepare(row['block_id'],row['profile_revision'],REPO)
                self.assertFalse(p['canonical_adapter_ready'])
    def test_pick_stops_held(self):
        p=self.plan();self.assertEqual(p['stages'][-1],'HOLD_CONFIRMED')
        self.assertFalse(set(p['stages']) & {'RELEASE_CONFIRMED','CENTER','LOWER230','AMR'})
        self.assertEqual(replay(p,self.evidence(p))['terminal_state'],'HELD_CONFIRMED')
    def test_place_release_before_retreat_before_center(self):
        p=self.plan('place',True);s=p['stages']
        self.assertLess(s.index('RELEASE_CONFIRMED'),s.index('RETREAT_CLEAR'))
        self.assertLess(s.index('RETREAT_CLEAR'),s.index('CENTER'))
        self.assertTrue(replay(p,self.evidence(p))['success'])
    def test_no_return_center_by_default(self):
        self.assertNotIn('CENTER',self.plan('place')['stages'])
    def test_failed_verification(self):
        p=self.plan();e=self.evidence(p);e[-2]['verified']=False
        self.assertFalse(replay(p,e)['success'])
    def test_release_unconfirmed(self):
        p=self.plan('place',True);e=self.evidence(p)
        e[p['stages'].index('RELEASE_CONFIRMED')]['verified']=False
        r=replay(p,e);self.assertFalse(r['success'])
        self.assertNotIn('CENTER',[v['stage'] for v in r['events']])
    def test_cancel_not_falsely_stopped(self):
        p=self.plan();r=replay(p,self.evidence(p),cancelled_at='CONTACT')
        self.assertEqual(r['terminal_state'],'UNCERTAIN');self.assertFalse(r['stop_confirmed'])
    def test_missing_evidence(self):
        p=self.plan();self.assertFalse(replay(p,[])['success'])
    def test_no_automatic_reset_after_hold(self):
        p=self.plan();e=self.evidence(p)+[dict(stage='LOWER230',verified=True)]
        self.assertFalse(replay(p,e)['success'])
    def test_payload_session_required(self):
        p=self.plan();e=self.evidence(p);e[-1].pop('payload_session_id')
        self.assertEqual(replay(p,e)['code'],'PAYLOAD_SESSION_REQUIRED')
    def test_revision_reject(self):
        with self.assertRaisesRegex(ValueError,'REVISION'):
            prepare('pick.scale.sieve.v1','WRONG',REPO)
    def test_new_station_unbound(self):
        with self.assertRaisesRegex(ValueError,'NOT_BOUND'):
            prepare('pick.dmp.sieve.v1','NOT_BOUND',REPO)
    def test_existing_utility_not_redispatched(self):
        with self.assertRaisesRegex(ValueError,'EXISTING'):
            prepare('utility.center_restore.right.v1','NOT_BOUND',REPO)
    def test_source_changed(self):
        row=next(r for r in registry() if r.get('profile_source'))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/row['profile_source'];p.parent.mkdir(parents=True);p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'SHA'):
                prepare(row['block_id'],row['profile_revision'],tmp)
    def test_pinned_source_bindings(self):
        for name,sha in json.loads((ROOT/'SOURCE_BINDINGS.json').read_text()).items():
            self.assertEqual(hashlib.sha256((REPO/name).read_bytes()).hexdigest(),sha)

if __name__=='__main__':unittest.main()
