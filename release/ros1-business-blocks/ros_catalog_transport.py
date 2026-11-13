#!/usr/bin/env python3
"""Real ROS service transport; default catalog node has no backend connection."""
import json
from pathlib import Path
import subprocess
import sys
import rospy
from ares_r_manipulation_blocks.srv import GetBlocks, PrepareBlock, GetPreparation

root=Path(__file__).resolve().parent
rospy.init_node('ares_catalog_transport_test',anonymous=True)
node=subprocess.Popen([sys.executable,str(root/'ros/ares_r_manipulation_blocks/scripts/block_catalog_node.py'),
                       '_contract_root:='+str(root)])
try:
    rospy.wait_for_service('/ares_r/blocks/list',timeout=20)
    result=rospy.ServiceProxy('/ares_r/blocks/list',GetBlocks)()
    blocks=json.loads(result.blocks_json)
    assert len(blocks)==11 and not any(b['physical_start_enabled'] for b in blocks)
    assert not json.loads(result.capabilities_json)['canonical_prepare_endpoint_configured']
    rospy.wait_for_service('/ares_r/blocks/prepare',timeout=5)
    result=rospy.ServiceProxy('/ares_r/blocks/prepare',PrepareBlock)('test','pick.scale.sieve.v1','old',True)
    assert not result.accepted and result.code=='CANONICAL_BACKEND_NOT_CONFIGURED'
    rospy.wait_for_service('/ares_r/blocks/preparation_status',timeout=5)
    result=rospy.ServiceProxy('/ares_r/blocks/preparation_status',GetPreparation)('unknown')
    assert not result.found
    print('ROS_CATALOG_TRANSPORT_PASS 3/3; physical_motion=false')
finally:
    node.terminate()
    node.wait(timeout=10)
