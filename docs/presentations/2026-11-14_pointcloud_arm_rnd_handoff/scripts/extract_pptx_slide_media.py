#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读提取PPTX指定幻灯片的关联媒体、页内文字与notes证据索引。

此工具不创建PPT、不向GitHub上传内容、不触发真实设备。
用法:
  python scripts/extract_pptx_slide_media.py \
    --pptx "/path/to/20261028-水分细度目标识别与场景自适应规划控制.pptx" \
    --out /tmp/ares_ppt_media --last 30

  python scripts/extract_pptx_slide_media.py \
    --pptx "/path/to/template.pptx" --out /tmp/template_scan --slides "1-4,6,8"

默认只保存关联图片/矢量文件；视频/音频会出现在manifest中，
但未获得授权不要放进公共仓库。对原件全文件计算SHA256便于溯源。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import posixpath
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SLIDE_RX = re.compile(r"^ppt/slides/slide([0-9]+)\.xml$")
DEFAULT_MAX_BYTES = 25 * 1024 * 1024
MEDIA_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif",
              ".webp", ".svg", ".emf", ".wmf"}
AUDIO_VIDEO_EXTS = {".mp4", ".m4v", ".mov", ".avi", ".wmv",
                    ".mp3", ".m4a", ".wav", ".wma"}


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def parse_selector(text: str) -> set[int]:
    result = set()
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            a, b = int(start), int(end)
            if a < 1 or b < a:
                raise ValueError("非法页范围: " + part)
            result.update(range(a, b + 1))
        else:
            n = int(part)
            if n < 1:
                raise ValueError("幻灯片号必须 >= 1")
            result.add(n)
    return result


def xml_text(data: bytes) -> str:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return ""
    vals = []
    for node in root.iter():
        if node.tag == "{" + A_NS + "}t" and node.text:
            vals.append(node.text)
    return "\n".join(vals)


def relationships(data: bytes, part_path: str) -> list[dict]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    entries = []
    for item in root.findall("{" + R_NS + "}Relationship"):
        target = item.get("Target", "")
        if not target or item.get("TargetMode") == "External":
            continue
        # ppt/slides/slideNN.xml -> ppt/slides/_rels/slideNN.xml.rels
        rootdir = posixpath.dirname(part_path)
        combined = posixpath.normpath(posixpath.join(rootdir, target.lstrip("/")))
        if target.startswith("/"):
            combined = target.lstrip("/")
        entries.append({
            "relation_id": item.get("Id", ""),
            "relation_type": item.get("Type", ""),
            "target": combined,
        })
    return entries


def safe_name(zip_path: str, sha: str) -> str:
    base = posixpath.basename(zip_path)
    base = re.sub(r"[^0-9A-Za-z_.-]", "_", base)
    return sha[:12] + "_" + base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pptx", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--last", type=int, help="按物理slide序号筛选最后N页")
    g.add_argument("--slides", type=str, help='页号或范围: "1-3,5,8-14"')
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES,
                        help="单个媒体最大提取字节数，默认25MiB")
    parser.add_argument("--include-av", action="store_true",
                        help="显式允许导出音视频（仅内部授权场景使用）")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not args.pptx.is_file() or not zipfile.is_zipfile(args.pptx):
        parser.error("输入PPTX不存在或不是有效ZIP: " + str(args.pptx))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "media").mkdir(exist_ok=True)
    (args.out / "slide_text").mkdir(exist_ok=True)
    ppt_sha = file_sha(args.pptx)

    with zipfile.ZipFile(args.pptx) as z:
        names = set(z.namelist())
        slides = sorted(
            (int(m.group(1)), name)
            for name in names
            if (m := SLIDE_RX.match(name))
        )
        if not slides:
            parser.error("PPTX没有找到ppt/slides/slideN.xml")

        if args.slides:
            wanted = parse_selector(args.slides)
        elif args.last is not None:
            if args.last < 1:
                parser.error("--last 必须>=1")
            wanted = {n for n, _ in slides[-args.last:]}
        else:
            wanted = {n for n, _ in slides}

        chosen = [(n, name) for n, name in slides if n in wanted]
        if not chosen:
            parser.error("页码范围没有匹配任何幻灯片")
        inventory = []
        slide_entries = []
        extracted_by_source = {}

        for n, slide_path in chosen:
            slide_text = xml_text(z.read(slide_path))
            rel_path = ("ppt/slides/_rels/" +
                        posixpath.basename(slide_path) + ".rels")
            rels = relationships(z.read(rel_path), slide_path) if rel_path in names else []
            note_text = ""
            for rel in rels:
                if "/notesSlides/" in rel["target"] and rel["target"] in names:
                    note_text = xml_text(z.read(rel["target"]))
                    break
            txt = args.out / "slide_text" / ("slide_%03d.txt" % n)
            if txt.exists() and not args.overwrite:
                raise FileExistsError(f"{txt} 已存在，使用--overwrite")
            txt.write_text(slide_text + "\n\n=== NOTES ===\n" + note_text,
                           encoding="utf-8")
            slide_item = {"slide_number": n, "slide_zip_path": slide_path,
                          "text_file": str(txt.relative_to(args.out)),
                          "media": []}
            for rel in rels:
                target = rel["target"]
                if not target.startswith("ppt/media/"):
                    continue
                if target not in names:
                    slide_item["media"].append({"source": target, "status": "MISSING_IN_ZIP"})
                    continue
                info = z.getinfo(target)
                suffix = posixpath.splitext(target)[1].lower()
                kind = ("AV" if suffix in AUDIO_VIDEO_EXTS else
                        "IMAGE" if suffix in MEDIA_EXTS else "OTHER")
                media = {"slide": n, "source": target, "kind": kind,
                         "zip_uncompressed_bytes": info.file_size,
                         "relation": rel["relation_id"]}
                if kind == "AV" and not args.include_av:
                    media["status"] = "SKIPPED_AV_REQUIRES_PERMISSION"
                elif kind == "OTHER":
                    media["status"] = "SKIPPED_OTHER"
                elif info.file_size > args.max_bytes:
                    media["status"] = "SKIPPED_SIZE"
                else:
                    if target in extracted_by_source:
                        media.update(extracted_by_source[target])
                    else:
                        h = hashlib.sha256()
                        temp = args.out / "media" / ("_tmp_slide_%03d" % n)
                        with z.open(target) as src, temp.open("wb") as dst:
                            for block in iter(lambda: src.read(1024 * 1024), b""):
                                h.update(block)
                                dst.write(block)
                        digest = h.hexdigest()
                        target_file = args.out / "media" / safe_name(target, digest)
                        if target_file.exists() and not args.overwrite:
                            temp.unlink(missing_ok=True)
                            raise FileExistsError(f"{target_file} 已存在，使用--overwrite")
                        temp.replace(target_file)
                        media.update({
                            "status": "EXTRACTED",
                            "sha256": digest,
                            "relative_path": str(target_file.relative_to(args.out)),
                        })
                        extracted_by_source[target] = {
                            "status": "EXTRACTED",
                            "sha256": digest,
                            "relative_path": str(target_file.relative_to(args.out)),
                        }
                slide_item["media"].append(media)
                inventory.append(media)
            slide_entries.append(slide_item)

    manifest = {
        "source_file": args.pptx.name, "source_sha256": ppt_sha,
        "source_bytes": args.pptx.stat().st_size,
        "slide_total": len(slides), "slide_selected": len(chosen),
        "media_extracted_unique": len(extracted_by_source),
        "warning": "仅作本地原件取证；不得未经审核上传视频、音频或私有现场截图。",
        "slides": slide_entries,
    }
    out_manifest = args.out / "manifest.json"
    if out_manifest.exists() and not args.overwrite:
        raise FileExistsError(f"{out_manifest} 已存在，使用--overwrite")
    out_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    with (args.out / "media_manifest.csv").open("w", newline="", encoding="utf-8-sig") as f:
        keys = ("slide", "source", "kind", "zip_uncompressed_bytes",
                "status", "sha256", "relative_path", "relation")
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(inventory)

    print("SOURCE_SHA256", ppt_sha)
    print("SLIDES", len(chosen), "/", len(slides))
    print("EXTRACTED_UNIQUE", len(extracted_by_source))
    print("OUTPUT", args.out / "manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
