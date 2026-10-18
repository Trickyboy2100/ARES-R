"""At-most-once dispatch records for canonical physical HTTP commands."""
import hashlib
import json
from pathlib import Path
import threading
from ares_r.manipulation.roundtrip_job import atomic


class PhysicalCommandLedger:
    def __init__(self,root):self.root=Path(root)/'worklog/runtime/physical-commands';self.lock=threading.Lock()
    def path(self,command_id):return self.root/(hashlib.sha256(command_id.encode()).hexdigest()+'.json')
    def read(self,command_id):
        path=self.path(command_id)
        return json.loads(path.read_text()) if path.exists() else {'state':'NOT_DISPATCHED','command_id':command_id}
    def reserve(self,command_id,kind,body):
        identity={k:v for k,v in body.items() if k not in ('cycle_token','authorization','onsite_observer_confirmed')}
        fingerprint=hashlib.sha256(json.dumps({'kind':kind,'body':identity},sort_keys=True).encode()).hexdigest()
        with self.lock:
            value=self.read(command_id)
            if value['state']!='NOT_DISPATCHED':
                if value['fingerprint']!=fingerprint:raise RuntimeError('COMMAND_ID_PAYLOAD_CHANGED')
                return False,value
            value={'command_id':command_id,'kind':kind,'fingerprint':fingerprint,'state':'DISPATCHING'}
            atomic(self.path(command_id),value);return True,value
    def update(self,command_id,state,result):
        with self.lock:
            value=self.read(command_id);value.update(state=state,result=result);atomic(self.path(command_id),value)
            return value
