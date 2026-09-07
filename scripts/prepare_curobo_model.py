#!/usr/bin/env python3
"""Fetch a pinned ARES model and prepare a six-joint PREVIEW-ONLY config.

Does not import or connect to JAKA. Requires PyYAML. Never marks a model commissioned.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

import yaml

REVISION = "b978cbd669b5a3f6bc0bd19defcbe5256692f145"


def download(name):
    url = ("https://api.github.com/repos/Trickyboy2100/ARES/contents/"
           "isaac_sim/simforge/robot/%s?ref=%s" % (name, REVISION))
    with urllib.request.urlopen(url, timeout=30) as response:
        return base64.b64decode(json.load(response)["content"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    # Refuse overwrites of previously prepared/site-edited models.
    root.mkdir(parents=True, exist_ok=False)
    original_urdf = download("jaka_minicobo_gripper.urdf")
    original_yaml = download("jaka_minicobo_curobo.yml")
    (root / "source.urdf").write_bytes(original_urdf)
    (root / "source.yml").write_bytes(original_yaml)
    robot = ET.fromstring(original_urdf)
    for link in robot.findall("link"):
        for item in list(link):
            if item.tag in ("visual", "collision"):
                link.remove(item)
    for joint in robot.findall("joint"):
        if joint.get("name", "").startswith("4C2_"):
            joint.set("type", "fixed")
            for item in list(joint):
                if item.tag in ("mimic", "limit", "axis"):
                    joint.remove(item)
    ET.ElementTree(robot).write(root / "robot.urdf", encoding="utf-8", xml_declaration=True)
    config = yaml.safe_load(original_yaml)
    kin = config["kinematics"]
    kin.update(urdf_path=str(root / "robot.urdf"), asset_root_path=str(root),
               load_meshes=False, mesh_link_names=None, lock_joints=None, tool_frames=["link6"])
    cspace = kin["cspace"]
    names = cspace["joint_names"]
    wanted = ["joint%d" % i for i in range(1, 7)]
    indexes = [names.index(n) for n in wanted]
    for key, value in list(cspace.items()):
        if isinstance(value, list) and len(value) == len(names):
            cspace[key] = [value[i] for i in indexes]
    cspace["joint_names"] = wanted
    (root / "robot.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    manifest = {"source_repository": "Trickyboy2100/ARES", "source_commit": REVISION,
                "source_urdf_sha256": hashlib.sha256(original_urdf).hexdigest(),
                "source_yaml_sha256": hashlib.sha256(original_yaml).hexdigest(),
                "commissioned": False,
                "limitations": ["unverified installed robot mapping", "unverified collision sphere coverage",
                                "gripper locked at model zero, not live opening", "no site obstacles",
                                "flange target, not live tool TCP"]}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(root / "robot.yml")


if __name__ == "__main__":
    main()
