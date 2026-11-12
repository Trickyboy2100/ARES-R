"""Same sphere/OBB SDF as NumPy reference, compiled CPU loop, no planner queries."""
import ctypes
import hashlib
from pathlib import Path
import subprocess
import tempfile
import os
import threading
import numpy as np

_lock=threading.Lock()
_library=None


def _kernel():
    global _library
    with _lock:
        if _library is not None:return _library
        source=Path(__file__).with_name('sphere_cuboid_cpu.cpp')
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        directory=Path(__file__).resolve().parents[3]/'worklog/runtime/collision_cpu'/digest
        directory.mkdir(parents=True,exist_ok=True)
        library=directory/'distance.so'
        if not library.exists():
            fd,tmp=tempfile.mkstemp(prefix='build-',suffix='.so',dir=str(directory));os.close(fd)
            try:
                subprocess.run(['c++','-O3','-std=c++11','-shared','-fPIC',str(source),'-o',tmp],
                               check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60,
                               env=dict(os.environ,PATH=os.environ.get('PATH') or os.defpath))
                os.replace(tmp,library)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
        handle=ctypes.CDLL(str(library))
        array=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
        integer=np.ctypeslib.ndpointer(dtype=np.int32,flags='C_CONTIGUOUS')
        handle.sphere_cuboid_cpu.argtypes=[array,array,array,ctypes.c_int,ctypes.c_int,ctypes.c_int,array,integer,array]
        handle.sphere_cuboid_cpu.restype=None
        _library=handle
        return handle


def distances(centers,radii,cuboids):
    xyz=np.ascontiguousarray(centers,dtype=np.float64)
    r=np.ascontiguousarray(radii,dtype=np.float64)
    if xyz.ndim!=3 or xyz.shape[-1]!=3 or xyz.shape[1]!=len(r) or not len(r):
        raise ValueError('NxSx3 centers and S radii required')
    if not np.isfinite(xyz).all() or not np.isfinite(r).all() or np.any(r<0):
        raise ValueError('finite nonnegative spheres required')
    from .independent_path_validation import _quaternion_rotation
    names=list(cuboids);rows=[]
    for box in cuboids.values():
        rows.append(list(box['pose'][:3])+_quaternion_rotation(box['pose'][3:]).reshape(-1).tolist()+list(box['dims']))
    boxes=np.ascontiguousarray(rows,dtype=np.float64).reshape(-1,15)
    if not np.isfinite(boxes).all() or np.any(boxes[:,12:]<=0):raise ValueError('invalid cuboids')
    gaps=np.empty(len(names),dtype=np.float64);indices=np.empty(len(names),dtype=np.int32)
    trace=np.empty(len(xyz),dtype=np.float64)
    _kernel().sphere_cuboid_cpu(xyz,r,boxes,len(xyz),len(r),len(names),gaps,indices,trace)
    return dict(zip(names,gaps.tolist())),dict(zip(names,indices.tolist())),trace.tolist()
