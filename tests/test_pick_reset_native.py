import importlib.util,unittest
from pathlib import Path
from ares_r.motion.latency_solver import cuboid_cache_capacity
spec=importlib.util.spec_from_file_location('pick_reset_pack',Path(__file__).resolve().parents[1]/'scripts/package_pick_reset_timing.py');pack=importlib.util.module_from_spec(spec);spec.loader.exec_module(pack)


class PickResetNativeTests(unittest.TestCase):
    def test_reverse_is_exact_same_samples_and_hash_bound(self):
        points=[[0.]*6,[.1]*6,[.2]*6];text='header\ntool\nlower\nupper\n'+'\n'.join(' '.join(str(x) for x in q) for q in points)+'\n'
        result,audit=pack.reverse_native(text,dict(native_path_sha256=pack.path_hash(points)),list(reversed(points)),'contact')
        self.assertEqual(result.splitlines()[4:],list(reversed(text.splitlines()[4:])))
        self.assertEqual(audit['native_path_sha256'],pack.path_hash(list(reversed(points))))
        with self.assertRaises(ValueError):pack.reverse_native(text,dict(native_path_sha256='bad'),list(reversed(points)),'contact')
    def test_capacity_floor_prevents_unnecessary_512_768_flip(self):
        self.assertEqual(cuboid_cache_capacity({},456),512)
        self.assertEqual(cuboid_cache_capacity({},505),768)
        for n in (456,505):self.assertEqual(cuboid_cache_capacity({'cuboid_capacity_floor':768},n),768)
        with self.assertRaises(ValueError):cuboid_cache_capacity({'cuboid_capacity_floor':513},3)
