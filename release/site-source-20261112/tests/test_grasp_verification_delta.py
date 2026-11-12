import json,unittest
from pathlib import Path

from ares_r.manipulation.grasp_verification import (
    classify_scene_delta,local_tcp_scene_delta,unexpected_added_fraction)

ROOT=Path(__file__).resolve().parents[1]
PARAMS=json.loads((ROOT/'config/tray_to_groove_v2.json').read_text())


def _grid(xs,ys,zs):
    return [[x,y,z] for x in xs for y in ys for z in zs]


def _span(lo,hi,step=.005):
    n=int(round((hi-lo)/step))+1
    return [lo+i*step for i in range(n)]


class OcclusionRevealTests(unittest.TestCase):
    """Lifting a basket uncovers the support underneath: that is not "unexpected"."""
    CENTER=[0.,0.,0.]
    #: the basket's side walls span the full height, exactly like the sieve
    WALLS=_grid([-.05,.05],_span(-.05,.05),_span(.02,.06))
    #: what the camera sees through the vacated basket afterwards
    FLOOR=_grid(_span(-.045,.045),_span(-.045,.045),[.02])
    FOREIGN=_grid(_span(.10,.14),_span(-.05,.05),_span(.02,.06))

    def test_revealed_support_below_the_payload_is_not_unexpected(self):
        delta=local_tcp_scene_delta(self.WALLS,self.FLOOR,self.CENTER)
        self.assertGreater(delta['added_fraction'],0.5,'the reveal alone exceeds the raw limit')
        self.assertEqual(delta['revealed_voxels'],delta['added_voxels'])
        self.assertEqual(delta['unexpected_added_voxels'],0)
        self.assertEqual(delta['unexpected_added_fraction'],0.0)
        self.assertGreaterEqual(delta['removed_fraction'],
                                PARAMS['grasp_verification']['minimum_removed_fraction'])
        self.assertEqual(classify_scene_delta(delta,PARAMS),'CHANGED_EXPECTED')

    def test_occupancy_outside_the_vacated_volume_is_still_unexpected(self):
        delta=local_tcp_scene_delta(self.WALLS,self.FLOOR+self.FOREIGN,self.CENTER)
        self.assertGreater(delta['revealed_voxels'],0)
        self.assertGreater(delta['unexpected_added_voxels'],0)
        self.assertGreater(delta['unexpected_added_fraction'],
                           PARAMS['grasp_verification']['maximum_unexpected_added_fraction'])
        self.assertEqual(classify_scene_delta(delta,PARAMS),'CHANGED_UNEXPECTED')

    def test_legacy_delta_without_refined_fields_falls_back(self):
        legacy={'before_voxels':100,'after_voxels':100,'removed_voxels':40,
                'removed_fraction':.4,'added_fraction':.9}
        self.assertEqual(unexpected_added_fraction(legacy),.9)
        self.assertEqual(classify_scene_delta(legacy,PARAMS),'CHANGED_UNEXPECTED')

    def test_nothing_removed_means_no_reveal_excuse(self):
        delta=local_tcp_scene_delta(self.WALLS,self.WALLS+self.FOREIGN,self.CENTER)
        self.assertEqual(delta['removed_voxels'],0)
        self.assertEqual(delta['revealed_voxels'],0)
        self.assertEqual(delta['unexpected_added_voxels'],delta['added_voxels'])


if __name__=='__main__':unittest.main()
