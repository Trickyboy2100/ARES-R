#!/usr/bin/env python3
"""Build pinned ARES mesh-derived collision metadata; never connects hardware."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
from ares_r.perception.robot_collision import _axis_rotation, _origin


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mesh_bounds(path):
    import open3d as o3d
    vertices = np.asarray(o3d.io.read_triangle_mesh(str(path)).vertices)
    if not len(vertices): raise ValueError("empty mesh: %s" % path)
    return vertices, vertices.min(axis=0), vertices.max(axis=0)


def gripper_transforms(root, opening):
    values = {"4C2_Joint1": opening, "4C2_Joint2": opening,
              "4C2_Joint3": -opening, "4C2_Joint4": -opening,
              "4C2_Joint5": opening, "4C2_Joint6": opening}
    transforms = {"link6": np.eye(4)}
    unresolved = {joint.get("name"): joint for joint in root.findall("joint")
                  if joint.find("child") is not None and
                  (joint.find("child").get("link", "").startswith("4C2_"))}
    while unresolved:
        progress = False
        for name, joint in list(unresolved.items()):
            parent = joint.find("parent").get("link"); child = joint.find("child").get("link")
            if parent not in transforms: continue
            transform = transforms[parent] @ _origin(joint)
            if joint.get("type") == "revolute":
                axis = [float(v) for v in joint.find("axis").get("xyz").split()]
                transform = transform @ _axis_rotation(axis, values[name])
            transforms[child] = transform; unresolved.pop(name); progress = True
        if not progress: raise RuntimeError("unresolved gripper URDF graph")
    return transforms


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(); root = args.asset_root.resolve()
    urdf = root / "jaka_minicobo_gripper.urdf"
    robot = ET.parse(str(urdf)).getroot(); hashes = {}; arm_boxes = {}; mesh_audit = {}
    for index in range(7):
        link = "base_link" if index == 0 else "link%d" % index
        path = root / "jaka_minicobo_meshes" / ("Link%d.STL" % index)
        vertices, low, high = mesh_bounds(path); hashes[str(path.relative_to(root))] = sha(path)
        arm_boxes[link] = {"center_m": ((low+high)/2).tolist(),
                           "half_extents_m": ((high-low)/2).tolist(),
                           "mesh": str(path.relative_to(root))}
        mesh_audit[link] = {"vertices": int(len(vertices)), "bounds_min_m": low.tolist(),
                            "bounds_max_m": high.tolist()}
    all_points=[]; gripper_mesh_audit={}; bounded_points={40:[],50:[]}
    for opening in (0.0, 0.41, 0.82):
        transforms = gripper_transforms(robot, opening)
        for link in ["4C2_baselink"] + ["4C2_Link%d" % i for i in range(1,7)]:
            path = root / "eg2_4c2_meshes" / (link+".STL")
            vertices, low, high = mesh_bounds(path); hashes[str(path.relative_to(root))] = sha(path)
            homogeneous = np.column_stack((vertices, np.ones(len(vertices))))
            all_points.append((transforms[link] @ homogeneous.T).T[:, :3])
            gripper_mesh_audit[link] = {"vertices": int(len(vertices)),
                                        "bounds_min_m": low.tolist(), "bounds_max_m": high.tolist()}
    for percent in bounded_points:
        for opening in np.linspace(0.0, .82*percent/100.0, 9):
            transforms = gripper_transforms(robot, float(opening))
            for link in ["4C2_baselink"] + ["4C2_Link%d" % i for i in range(1,7)]:
                vertices, _, _ = mesh_bounds(root / "eg2_4c2_meshes" / (link+".STL"))
                homogeneous = np.column_stack((vertices, np.ones(len(vertices))))
                bounded_points[percent].append(
                    (transforms[link] @ homogeneous.T).T[:, :3])
    points=np.concatenate(all_points); low=points.min(0); high=points.max(0)
    hashes[urdf.name]=sha(urdf); hashes["jaka_minicobo_curobo.yml"]=sha(root/"jaka_minicobo_curobo.yml")
    payload={"schema_version":1,"asset_revision":"Trickyboy2100/ARES@b978cbd669b5a3f6bc0bd19defcbe5256692f145",
             "asset_root":str(root),"urdf":urdf.name,"asset_sha256":hashes,
             "arm_link_boxes":arm_boxes,
             "gripper_max_envelope_link6":{"center_m":((low+high)/2).tolist(),
                 "half_extents_m":((high-low)/2).tolist(),"opening_samples_rad":[0.0,0.41,0.82],
                 "source":"union of all pinned EG2-4C2 meshes over full opening range"},
             "gripper_envelopes_link6_by_max_opening_percent":{},
             "mesh_audit":{"arm":mesh_audit,"gripper":gripper_mesh_audit},
             "fixed_body_boxes":[
                 {"geometry_id":"body/chassis","owner":"chassis","kind":"chassis_conservative_proxy",
                  "center_body_m":[-0.16,0.0,0.575],"dims_m":[0.56,0.70,1.15],"filter_owned":True,
                  "source":"CONSERVATIVE_PROXY pending measured AGV CAD"},
                 {"geometry_id":"body/central_exclusion","owner":"safety","kind":"central_exclusion",
                  "center_body_m":[0.45,0.0,1.2],"dims_m":[1.8,0.14,2.4],"filter_owned":False,
                  "source":"hard BODY |Y|<=0.070 m safety constraint; not physical self-filter"}],
             "classifications":{"arm_kinematics":"VALIDATED_AFTER_SITE_CHECK",
                 "arm_mesh_boxes":"VALIDATED_AFTER_SITE_CHECK","legacy_curobo_spheres":"MISSING_BLOCKER",
                 "gripper_mesh_mount":"VALIDATED_AFTER_SITE_CHECK","gripper_opening":"CONSERVATIVE_PROXY",
                 "tool_tcp":"VALIDATED_AFTER_SITE_CHECK","body_base_transforms":"VALIDATED_AFTER_SITE_CHECK",
                 "chassis":"CONSERVATIVE_PROXY"}}
    for percent, rows in bounded_points.items():
        bounded=np.concatenate(rows); bounded_low=bounded.min(0); bounded_high=bounded.max(0)
        payload["gripper_envelopes_link6_by_max_opening_percent"][str(percent)] = {
            "center_m":((bounded_low+bounded_high)/2).tolist(),
            "half_extents_m":((bounded_high-bounded_low)/2).tolist(),
            "opening_range_rad":[0.0,.82*percent/100.0],
            "source":"union of pinned EG2-4C2 meshes sampled over 0..%d percent opening"%percent}
    payload["geometry_revision"]="sha256:"+hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(args.output),"geometry_revision":payload["geometry_revision"],
                      "gripper_envelope_dims_m":(high-low).tolist()}))


if __name__ == "__main__": main()
