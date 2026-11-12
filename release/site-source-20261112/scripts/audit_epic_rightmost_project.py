#!/usr/bin/env python3
"""Export the ATOM rightmost-placement graph without editing Epic/ATOM."""

import argparse,json
from pathlib import Path
import sys,time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from ares_r.adapters.atom_project import AtomProjectClient


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--host",default="192.168.99.199")
    args=parser.parse_args();client=AtomProjectClient(args.host)
    graphs=client.list_graphs();name="物料放置最右点"
    if name not in [item.get("graphName") for item in graphs]:
        raise RuntimeError("ATOM graph not found: "+name)
    opened=client.open_graph(name);graph=opened["graph"]
    sorters=[node for node in graph["NODES"].values()
             if node.get("type")=="PickPointSorterNew"]
    result={"schema_version":1,"captured_at_unix":time.time(),
        "read_only":True,"flow_name":name,"graph_version":graph.get("VERSION"),
        "atom_output_present":any(node.get("type")=="EpicProOutput"
                                  for node in graph["NODES"].values()),
        "sorter_parameters":[item.get("run_params") for item in sorters],
        "candidate":{"space_id":2,"object_id":3,"camera_id":1,
                     "command":"320,2,3,1,1,0"},
        "epic_binding_exposed_by_atom_graph":False,
        "commissioned":False,
        "missing":"EpicPro UI mapping from flow name to space/object/camera and pose-axis semantics",
        "raw_graph":graph}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({key:result[key] for key in result if key!="raw_graph"},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
