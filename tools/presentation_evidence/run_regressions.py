"""Run relevant repository unittest groups inside offline_sandbox.sh."""
import argparse,sys,unittest,io,re,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tests'));sys.path.insert(0,str(ROOT/'src'))
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(exist_ok=True,parents=True);rows=[];ok=True
for name,modules in [('regression',['test_support_decomposition','test_robot_owned_filter','test_contact_spatial_index','test_cpu_distance','test_p39_task_studio','test_demo_workbench','test_workbench_http']),('joint_mapping_tests',['test_planner_joint_mapping'])]:
 stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(modules));text=stream.getvalue().replace(str(ROOT),'REPOSITORY');text=re.sub(r'/home/[^/\s]+/','/controlled-user/',text);log=a.output/(name+'.log');log.write_text(text);rows.append(dict(group=name,count=r.testsRun,result='PASS' if r.wasSuccessful() else 'FAIL',log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()));ok&=r.wasSuccessful()
(a.output/'regression_summary.json').write_text(json.dumps(dict(tests=rows,hardware_io=False,runner='unittest under network/serial isolation'),indent=2)+'\n');print(json.dumps(rows));sys.exit(not ok)
