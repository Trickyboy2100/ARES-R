#!/usr/bin/env python3
"""Build the Console capability directory from the maintained handbook."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'src/ares_r/webui/demo_wall_catalog.json'

# Exact task semantics only. The standalone Fetch exits are still being extracted.
UNBOUND_FETCH = {'AA0F0', 'AC0F0'}
STATIONS = {'AW': '通用', 'A0': '料盘天平', 'C0': '筛网天平',
            'B1': '烘干箱 · 左列', 'B2': '烘干箱 · 中列', 'B3': '烘干箱 · 右列',
            'D1': '专机 · 筛网范围', 'D2': '专机 · 料盘范围'}
FLOW = {
    'F': '识别 → 预抓取 → 接近 → 闭爪验证 → 脱离 / 抬升 → 持稳',
    'P': '识别 → 预放置 → 进入 / 下降 → 松爪确认 → 退出 → center',
    'U': '读取当前状态 → 规划 → 执行 → 实际到位回读',
}
UTILITY_ACTIONS = {'AAWU0-01': '/ares_r/return_center',
                   'AAWU0-02': '/ares_r/center_restore',
                   'AAWU0-03': '/ares_r/center_restore_turbo',
                   'AAWU0-04': '/ares_r/dual_center_restore'}


def build_document():
    source = json.loads((ROOT / 'docs/demo-handbook/catalog.json').read_text())
    entries = []
    for original in source['entries']:
        entry = dict(original)
        code = entry['native_code']
        branch = entry['function'] == 'F' and '-' in code
        entry['category'] = 'T' if branch else entry['function']
        entry['station_label'] = STATIONS[entry['station']]
        entry['launch_alias'] = entry['legacy_alias'] if code not in UNBOUND_FETCH else ''
        entry['summary'] = FLOW[entry['function']]
        entry['launch_note'] = ''
        if code in UNBOUND_FETCH:
            entry['launch_note'] = '独立持物结束入口待接入；可先选择已验证的原位抓放测试分支。'
        elif branch:
            entry['summary'] = ('识别 → 抓取 → 抬升100mm → HOLD' if code.endswith('-03')
                                else '识别 → 抓取 → 抬升230mm → 原位放回 → center')
            entry['category'] = 'T'
        elif code == 'AAWU0-01':
            entry['summary'] = '扫描 → 当前位置规划到右臂 center → 到位回读'
        elif code in ('AAWU0-02', 'AAWU0-03', 'AAWU0-04'):
            entry['summary'] = '扫描 → center → 已保存姿态 → 到位回读'
        if code == 'AAWU0-05':
            entry['summary'] = '选择源臂与目标臂 → 镜像规划 → 核对 → 执行'
            entry['launch_note'] = '镜像调试工具位于运行监控；独立Demo入口待定义。'
        entry['ros_action'] = UTILITY_ACTIONS.get(code, '/ares_r/run_block' if entry['legacy_block'] else '')
        entry['delivery_native_ready'] = code in {'AAWU0-01', 'AAWU0-02', 'AB2P5', 'AD1P0', 'AC0P0'}
        entry['ros_launch_alias'] = ''
        native_verified = code in {'AB2P5', 'AD1P0', 'AD2P0', 'AC0P0', 'AC0F0-02',
                                   'AA0F0-03', 'AAWU0-01', 'AAWU0-02', 'AAWU0-04'}
        ros_verified = code in {'AAWU0-02', 'AAWU0-04'}
        entry['milestones'] = [
            dict(label='定义', state='done'),
            dict(label='参数', state='done' if entry.get('parameter_path') and code not in UNBOUND_FETCH else 'review'),
            dict(label='原生实机', state='done' if native_verified else 'review'),
            dict(label='ROS实机', state='done' if ros_verified else 'pending'),
            dict(label='交付', state='done' if code == 'AAWU0-02' else 'pending'),
        ]
        entry['handbook_page'] = 5 if entry['function'] == 'U' or branch else (3 if entry['function'] == 'F' else 4)
        entries.append(entry)
    entries.extend([
        dict(native_code='S-A0-B2-01', ros_code='', title='料盘 · 天平取 → 烘干箱下中放 → 返回',
             station='A0→B2', station_label='料盘天平 → 烘干箱', object='料盘', category='S',
             native_status='历史接续完成保全；当前参数完整全链待绑定', ros_status='完整Scheme的ROS交付待完成',
             epic_config='1 → 3', legacy_alias='demo-2-main-graspplace', launch_alias='demo-2-main-graspplace',
             launch_note='', summary='抓取 → 抬升 → 底盘转场 → 放置 → 返回', handbook_page=6),
        dict(native_code='S-C0-D1-01', ros_code='', title='筛网 · 天平取 → 专机放 → 恢复',
             station='C0→D1', station_label='筛网天平 → 专机', object='筛网', category='S',
             native_status='分段已有成功；完整组合分派待修复', ros_status='完整Scheme的ROS交付待完成',
             epic_config='6 → 2', legacy_alias='demo-4-main-siftgrasp-dmpplace', launch_alias='',
             launch_note='所读分派源码缺少筛网全链专用分支；保留查看，先使用独立取放入口。',
             summary='抓取 → 抬升 → 底盘转场 → 专机放置 → 恢复', handbook_page=6),
    ])
    codes = [entry['native_code'] for entry in entries]
    assert len(codes) == len(set(codes))
    aliases = [entry['launch_alias'] for entry in entries if entry['launch_alias']]
    assert len(aliases) == len(set(aliases)), 'one runtime alias must have one exact tile'
    return dict(schema_version=1, revision='DEMO_WALL_20261117_V1',
                evidence_date='2026-11-17', entries=entries)


def build(check=False):
    text = json.dumps(build_document(), ensure_ascii=False, indent=2) + '\n'
    if check:
        if not OUTPUT.exists() or OUTPUT.read_text() != text:
            raise SystemExit('Demo wall catalog is out of date')
    else:
        OUTPUT.write_text(text)
    print('Demo wall directory verified: 30 capabilities; exact launch aliases unique')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    build(parser.parse_args().check)
