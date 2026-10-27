"""Local workstation identity only. Never probes any network/device endpoint."""
import importlib.metadata,os,platform,json,time,subprocess,sys
from pathlib import Path
import torch
versions={}
for module in ['torch','numpy','scipy','open3d','matplotlib','PyYAML','Pillow','warp-lang']:
 try:versions[module]=importlib.metadata.version(module)
 except importlib.metadata.PackageNotFoundError:versions[module]=None
cpu=next(x.split(':',1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name'))
gpu=torch.cuda.is_available();record=dict(source_kind='FROZEN_REPLAY',utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),os=platform.freedesktop_os_release().get('PRETTY_NAME'),kernel=platform.release(),python=platform.python_version(),cpu=cpu,cpu_logical=os.cpu_count(),versions=versions,OMP_NUM_THREADS=os.getenv('OMP_NUM_THREADS'),OPENBLAS_NUM_THREADS=os.getenv('OPENBLAS_NUM_THREADS'),cuda_available=gpu,cuda_runtime=torch.version.cuda,physical_motion=False)
if gpu:record.update(gpu=torch.cuda.get_device_name(0),cuda_visible_devices=os.getenv('CUDA_VISIBLE_DEVICES'),gpu_total_bytes=torch.cuda.get_device_properties(0).total_memory,free_total_bytes_after_torch_init=list(torch.cuda.mem_get_info()))
record['driver_query']=subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,memory.total,memory.used','--format=csv,noheader'],text=True).strip()
Path(sys.argv[1]).write_text(json.dumps(record,indent=2)+'\n')
