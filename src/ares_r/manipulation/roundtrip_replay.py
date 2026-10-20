"""Stateful, hardware-free CycleRunner transport using the replay provider.

This verifies task ordering/parameters only. It makes no GPU, grasp, collision,
telemetry or site claim. No real service bundle can be supplied to this class.
"""
import math
from ares_r.skills.providers import ReplayCapabilityProvider


class RoundtripReplayTransport(ReplayCapabilityProvider):
    revision='roundtrip-state-replay-v1'
    def __init__(self,parameters,*,fault_stage=None):
        super().__init__();self.parameters=parameters;self.fault_stage=fault_stage
        self.stage=None;self.prepared=False;self.pose='START';self.open=False
        self.closed=False;self.hold_candidate=False;self.attached=False
        self.height_m=0.;self.base_pose=[0.,0.,0.];self.preland=False;self.stopped=False
    def check_cancelled(self):
        if self.stopped:raise RuntimeError('REPLAY_STOPPED')
    def stop(self):self.stopped=True
    def _record(self,call,**args):
        self.check_cancelled()
        if self.fault_stage is not None and self.stage==self.fault_stage:
            raise RuntimeError('INJECTED_REPLAY_FAULT:'+self.stage)
        self.calls.append((call,args))
        return {'mock':True,'evidence_kind':'STATE_MACHINE_ONLY','call':call,'arguments':args}
    def prepare_pick(self):
        result=self._record('prepare_pick');self.prepared=True;return result
    def move_center(self):
        if self.attached:raise RuntimeError('empty-gripper center requires no attachment')
        result=self._record('move_center');self.pose='CENTER';return result
    def pick_segment(self,segment):
        result=self._record('pick_segment',segment=segment)
        if segment=='pregrasp':
            if not self.prepared:raise RuntimeError('pick not prepared')
            self.pose='PREGRASP'
        elif segment=='contact':
            if self.pose!='PREGRASP' or not self.open:raise RuntimeError('contact state mismatch')
            self.pose='CONTACT'
        elif segment in ('lift','lift230'):
            if not self.hold_candidate:raise RuntimeError('hold candidate required')
            self.height_m=.23 if segment=='lift230' else .1;self.pose='LIFT230' if segment=='lift230' else 'LIFT100'
        else:raise ValueError('unknown segment')
        return result
    def gripper(self,raw):
        result=self._record('gripper',raw=raw)
        if raw==self.parameters['gripper_closed_raw']:
            if self.pose!='CONTACT':raise RuntimeError('close before contact')
            self.closed=True;self.open=False
        else:
            if self.closed and not self.preland:raise RuntimeError('release before preland')
            if self.closed and self.parameters.get('place_descent_enabled') and not getattr(self,'descended',False):
                raise RuntimeError('release before descent')
            self.open=True;self.closed=False
        return result
    def verify_grasp(self):
        result=self._record('verify_grasp')
        if not self.closed:raise RuntimeError('gripper is not closed')
        self.hold_candidate=True;return result
    def attach(self):
        result=self._record('attach')
        if self.pose not in ('LIFT100','LIFT230') or not self.hold_candidate:raise RuntimeError('attach before initial lift')
        self.attached=True;return result
    def lift_remaining(self,distance_m):
        result=self._record('lift_remaining',distance_m=distance_m)
        if not self.attached or not math.isclose(distance_m,.13):raise RuntimeError('remaining lift mismatch')
        self.height_m+=distance_m;return result
    def base(self,delta):
        result=self._record('base',delta=delta)
        if not math.isclose(self.height_m,.23):raise RuntimeError('base before HOLD230')
        self.base_pose=[a+b for a,b in zip(self.base_pose,delta)];return result
    def place_target(self,slot_id,height_m):
        result=self._record('place_target',slot_id=slot_id,height_m=height_m)
        if slot_id!='lower_middle' or not math.isclose(height_m,.04):raise RuntimeError('placement contract changed')
        expected=self.parameters.get('place_station_net_body_m',[0,-.85,0])
        if max(abs(a-b) for a,b in zip(self.base_pose,expected))>1e-9:raise RuntimeError('base not at PLACE')
        self.target_ready=True;return result
    def move_preland(self):
        result=self._record('move_preland')
        if not self.attached or not getattr(self,'target_ready',False):raise RuntimeError('place target unavailable')
        self.preland=True;return result
    def detach(self):
        result=self._record('detach')
        if not self.open:raise RuntimeError('detach before release')
        self.attached=False;return result
    def place_descend(self,distance_m):
        result=self._record('place_descend',distance_m=distance_m)
        if not self.attached or not self.preland:raise RuntimeError('descent before preland')
        if not math.isclose(distance_m,self.parameters['place_descent_m']):raise RuntimeError('descent distance mismatch')
        self.descended=True;return result
