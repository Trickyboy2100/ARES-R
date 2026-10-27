"""Assert offline namespace/device isolation without sending network requests."""
import json,sys,os
from pathlib import Path
route_lines=Path('/proc/net/route').read_text().splitlines()[1:]
interfaces=[x.split(':',1)[0].strip() for x in Path('/proc/net/dev').read_text().splitlines()[2:]]
serial=[str(x) for pattern in ['ttyUSB*','ttyACM*','hidraw*'] for x in Path('/dev').glob(pattern)]
gpus=[x.name for x in Path('/dev').glob('nvidia[0-9]*')]
assert not route_lines and all(x=='lo' for x in interfaces) and not serial and gpus==['nvidia0'],(interfaces,serial,gpus)
record=dict(network_routes=route_lines,network_interfaces=interfaces,physical_serial_devices=serial,gpu_devices=gpus,offline_guard=os.getenv('ARES_R_OFFLINE_REPLAY'),cuda_visible=os.getenv('CUDA_VISIBLE_DEVICES'),test='Read /proc namespace state and private /dev; no connect/capture/execution calls',result='PASS')
Path(sys.argv[1]).write_text(json.dumps(record,indent=2)+'\n')
