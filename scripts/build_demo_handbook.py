#!/usr/bin/env python3
"""Build the documentation-only Demo handbook with no runtime dependencies."""
import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/demo-handbook'
OUTPUT = ROOT / 'src/ares_r/webui/demo_handbook.html'
PAGES = [
    ('README.md', '开始阅读'),
    ('01-naming.md', '编号与工位'),
    ('02-catalog.md', '全部功能目录'),
    ('03-fetch.md', '取 · Fetch'),
    ('04-place.md', '放 · Place'),
    ('05-utility.md', 'Utility 与测试分支'),
    ('06-handover.md', '交接高度与转场'),
    ('07-delivery.md', 'ROS 交付流程'),
    ('08-evidence.md', '证据与参数索引'),
    ('09-maintenance.md', '维护与下一步'),
]


def pair(entry):
    return '`{native_code}` / `{ros_code}`'.format(**entry)


def table(headers, rows):
    lines = ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |']
    for row in rows:
        lines.append('| ' + ' | '.join(str(cell).replace('|', '&#124;') for cell in row) + ' |')
    return '\n'.join(lines)


def catalog_markdown(entries):
    business = [entry for entry in entries if '-' not in entry['native_code']]
    rows = []
    for fetch in business:
        if fetch['function'] != 'F':
            continue
        place = next(entry for entry in business if entry['station'] == fetch['station'] and entry['slot'] == fetch['slot'] and entry['function'] == 'P')
        rows.append([fetch['station'] + ' · ' + fetch['title'].replace('取料并持稳', '').replace('取料盘', '料盘').replace('取筛网', '筛网'), pair(fetch), pair(place), fetch['native_status'], place['native_status']])
    utility = [entry for entry in entries if entry['function'] == 'U']
    variants = [entry for entry in entries if entry['function'] == 'F' and '-' in entry['native_code']]
    parts = [
        '# 全部功能目录',
        '本页由 `catalog.json` 生成。A/R 编号同格，取放同一行。编号为文档映射；ROS列包含最终交付目标，具体可用性以状态列为准。',
        '## 20项业务能力 · 10取 + 10放',
        '天平与专机共8项，烘干箱六取六放共12项。旧P05/L03已归入六槽系列，作为兼容入口记录。',
        table(['范围 / 对象', '取 · 原生 / ROS', '放 · 原生 / ROS', '取的原生依据', '放的原生依据'], rows),
        '## ROS封装进度',
        table(['业务', '原生 / ROS', '既有模块', 'ROS进度'], [[entry['title'], pair(entry), entry['legacy_block'], entry['ros_status']] for entry in business]),
        '## Utility',
        table(['功能', '原生 / ROS', '原生依据', 'ROS进度'], [[entry['title'], pair(entry), entry['native_status'], entry['ros_status']] for entry in utility]),
        '## 验证分支与历史Golden',
        table(['功能', '原生 / ROS预留', '原生依据', '旧入口'], [[entry['title'], pair(entry), entry['native_status'], '`' + entry['legacy_alias'] + '`'] for entry in variants]),
        '## 优先复用',
        'AB2P5（烘干箱下中）、AD1P0（筛网专机）、AC0P0（筛网天平）已有完整原生实机依据。AD2P0已有完整成功但当前参数版本需回溯绑定。A0/C0独立Fetch从已成功抓取段提取持物结束出口。其余烘干箱泊位从成熟算法与动作合同派生，分别绑定偏置和验收。',
        'D1/D2为本版分配提案；Utility-05为预留能力。全部清单包含开发与交付目标，Delivered状态仅在明确交付项上成立。',
    ]
    return '\n\n'.join(parts) + '\n'


def evidence_markdown(entries):
    parts = ['# 参数、证据与旧入口索引',
             '依据2026-11-17现场只读快照和已保存ROS报告。当前参数SHA与历史运行结果分别记录；缺少当次参数快照时，当前SHA不能代替历史绑定。现场证据根目录为 `/home/yikun/ARES-R-RC1-20261019`。',
             '## 数据来源',
             '`docs/reports/2026-11-17_DEMO_CONSOLE_TASK_TEMPLATE_AND_PHYSICAL_BASELINE.md`、`docs/reports/2026-11-17_ROS_DEMO_CONSOLE_INVENTORY.md`、`worklog/evidence/2026-11-17-demo-console-task-audit/demo-task-matrix.json`。原始私有快照另行归档。',
             '## 已映射业务']
    for entry in entries:
        parts.extend(['### ' + entry['native_code'] + ' · ' + entry['title'],
                      '对应ROS `' + entry['ros_code'] + '`；原生状态 ' + entry['native_status'] + '；ROS状态 ' + entry['ros_status'] + '。'])
        if entry['legacy_alias']:
            parts.append('旧Console入口 `' + entry['legacy_alias'] + '`。')
        if entry.get('demo_id'):
            parts.append('执行Demo `' + entry['demo_id'] + '`。')
        if entry.get('parameter_path'):
            parts.append('当前参数 `' + entry['parameter_path'] + '`。')
            parts.append('revision `' + str(entry.get('current_parameter_revision', '待绑定')) + '`。')
            parts.append('SHA256 `' + str(entry.get('current_parameter_sha256', '待绑定')) + '`。')
        records = entry.get('evidence_paths', [])
        if records:
            parts.append('采集到的成功记录索引（包含各记录声明的阶段范围）')
            parts.extend('- `' + path + '`' for path in records)
        else:
            parts.append('完整证据路径需从对应Utility报告或后续新增运行绑定；当前条目的状态依据见总表。')
    parts.extend(['## 关键完整成功结果',
                  '- 筛网专机 `right_arm_dmp_place_v1/run_1794204348793064700/result.json`，PLACE_CENTER_COMPLETE。',
                  '- 料盘专机 `right_arm_liaopan_dmp_place_v1/run_1794216841515922914/result.json`，PLACE_CENTER_COMPLETE。',
                  '- 料盘烘干箱下中 `right_arm_liaopan_hongganxiang_place/run_1794383252441911735/result.json`，PLACE_CENTER_COMPLETE。',
                  '- 筛网天平 `right_arm_shaiwang_cheng_place_v1/run_1794554796221507249/result.json`，PLACE_CENTER_COMPLETE。',
                  '以上路径位于现场 `worklog/evidence/demo-runs/` 下。最近一次运行、完整成功、当前接受版本分别维护。'])
    return '\n\n'.join(parts) + '\n'


def inline(text):
    """Escape text and render the small Markdown subset used by this handbook."""
    tokens = re.split(r'(`[^`]+`|\[[^\]]+\]\([^)]+\))', text)
    result = []
    for token in tokens:
        if token.startswith('`') and token.endswith('`'):
            result.append('<code>' + html.escape(token[1:-1]) + '</code>')
        elif re.fullmatch(r'\[[^\]]+\]\([^)]+\)', token):
            label, target = re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)', token).groups()
            page = next((index for index, (name, _) in enumerate(PAGES) if name == target), None)
            if page is None:
                raise ValueError('Unresolved handbook link: ' + target)
            result.append('<a href="#page-' + str(page) + '">' + html.escape(label) + '</a>')
        else:
            result.append(html.escape(token))
    return ''.join(result)


def render_markdown(text):
    lines = text.splitlines()
    rendered = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith('```'):
            index += 1
            code = []
            while index < len(lines) and not lines[index].startswith('```'):
                code.append(lines[index])
                index += 1
            rendered.append('<pre><code>' + html.escape('\n'.join(code)) + '</code></pre>')
        elif line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            rendered.append('<h{0}>{1}</h{0}>'.format(level, inline(line[level:].strip())))
        elif line.startswith('|'):
            rows = []
            while index < len(lines) and lines[index].startswith('|'):
                cells = [cell.strip() for cell in lines[index].strip('|').split('|')]
                if not all(re.fullmatch(r'[-: ]+', cell) for cell in cells):
                    rows.append(cells)
                index += 1
            rendered.append('<div class="table-wrap"><table><thead><tr>' + ''.join('<th>' + inline(cell) + '</th>' for cell in rows[0]) + '</tr></thead><tbody>')
            for row in rows[1:]:
                rendered.append('<tr>' + ''.join('<td>' + inline(cell) + '</td>' for cell in row) + '</tr>')
            rendered.append('</tbody></table></div>')
            continue
        elif line.startswith('- ') or re.match(r'^\d+\. ', line):
            ordered = not line.startswith('- ')
            tag = 'ol' if ordered else 'ul'
            pattern = r'^\d+\. ' if ordered else r'^- '
            rendered.append('<' + tag + '>')
            while index < len(lines) and re.match(pattern, lines[index]):
                rendered.append('<li>' + inline(re.sub(pattern, '', lines[index])) + '</li>')
                index += 1
            rendered.append('</' + tag + '>')
            continue
        else:
            rendered.append('<p>' + inline(line) + '</p>')
        index += 1
    return '\n'.join(rendered)


STYLE = '''
[hidden]{display:none!important}:root{color-scheme:light;--ink:#172d40;--muted:#566a7b;--line:#d8e2e9;--accent:#116b83}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:#f3f6f8;font:15px/1.75 "Inter",system-ui,-apple-system,sans-serif}a{color:var(--accent);text-underline-offset:3px}header{height:66px;display:flex;align-items:center;gap:22px;padding:0 28px;background:#122a3b;color:white;position:sticky;top:0;z-index:3}header a{color:#bce9f7}header strong{font-size:18px}.version{margin-left:auto;font-size:12px;color:#c4d5e0}button,input{font:inherit}button{cursor:pointer;border:1px solid var(--line);border-radius:6px;padding:7px 12px;background:white;color:var(--ink)}.layout{max-width:1680px;margin:auto;display:grid;grid-template-columns:260px minmax(0,1fr);gap:28px;padding:24px}aside{position:sticky;top:90px;align-self:start;max-height:calc(100vh - 110px);overflow:auto}input{width:100%;padding:10px;border:1px solid #b7cbd5;border-radius:6px;margin-bottom:14px;background:white}nav a{display:block;padding:9px 13px;text-decoration:none;border-left:3px solid transparent;color:#375164;margin:3px 0}nav a[aria-current=page]{background:#dcecf1;color:#064b61;border-color:#16748d;font-weight:650}.note{font-size:12px;color:var(--muted);padding:10px 13px}.page{background:white;border:1px solid var(--line);border-radius:10px;padding:30px 38px;min-width:0}.page[hidden]{display:none}h1{font-size:29px;line-height:1.4;margin:0 0 24px}h2{font-size:21px;margin-top:34px;border-top:1px solid var(--line);padding-top:22px}h3{font-size:17px;margin-top:28px}p,li{max-width:100ch}code{font:12px/1.6 "IBM Plex Mono",ui-monospace,monospace;background:#edf3f6;padding:2px 4px;border-radius:3px;overflow-wrap:anywhere}pre{background:#edf3f6;padding:16px;overflow:auto}pre code{white-space:pre}.table-wrap{overflow:auto;margin:16px 0}table{border-collapse:collapse;width:100%;min-width:660px;font-size:13px}td,th{border:1px solid var(--line);padding:10px 12px;text-align:left;vertical-align:top}th{background:#eaf2f5}tr:nth-child(even){background:#f8fafb}.pager{display:flex;justify-content:space-between;gap:20px;margin:35px 0 0;border-top:1px solid var(--line);padding-top:22px}.pager a{max-width:48%}.source{font-size:12px;color:var(--muted);overflow-wrap:anywhere}#searchStatus{font-size:12px;min-height:20px;color:var(--muted)}@media(max-width:900px){.layout{grid-template-columns:200px minmax(0,1fr);gap:16px;padding:16px}.page{padding:22px}header{padding:0 16px;gap:12px}.version{display:none}}@media(max-width:650px){header{height:auto;min-height:66px;flex-wrap:wrap;padding:12px}.layout{display:block}aside{position:static;max-height:none;margin-bottom:18px}nav{display:flex;flex-wrap:wrap}nav a{font-size:13px;padding:5px 8px}.note{display:none}.page{padding:20px 16px}h1{font-size:24px}}@media print{header,aside,.pager{display:none}.layout{display:block;padding:0}.page,.page[hidden]{display:block!important;border:0;break-before:page;padding:0}.table-wrap{overflow:visible}table{min-width:0}body{font-size:11px;background:white}code{font-size:10px}}
'''
SCRIPT = '''
const pages=[...document.querySelectorAll('.page')];
const links=[...document.querySelectorAll('nav a')];
function showPage(){
 const wanted=location.hash.slice(1)||'page-0';
 const selected=pages.find(p=>p.dataset.route===wanted)||pages[0];
 pages.forEach(p=>p.hidden=p!==selected);
 links.forEach(a=>{if(a.hash==='#'+selected.dataset.route)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
 document.title=selected.querySelector('h1').textContent+' · ARES-R';
 window.scrollTo(0,0);
}
window.addEventListener('hashchange',showPage);
document.querySelector('#search').addEventListener('input',event=>{
 const query=event.target.value.trim().toLowerCase();let count=0;
 links.forEach((a,index)=>{const match=!query||pages[index].textContent.toLowerCase().includes(query);a.hidden=!match;if(match)count++});
 document.querySelector('#searchStatus').textContent=query?count+' 个章节匹配，点击目录查看':'';
});
document.querySelector('#print').addEventListener('click',()=>window.print());showPage();
'''


def validate(catalog):
    entries = catalog['entries']
    for field in ('native_code', 'ros_code'):
        codes = [entry[field] for entry in entries]
        if len(set(codes)) != len(codes):
            raise ValueError('Duplicate ' + field)
    business = [entry for entry in entries if '-' not in entry['native_code']]
    assert len(business) == 20
    assert sum(entry['function'] == 'F' for entry in business) == 10
    for entry in entries:
        assert re.fullmatch(r'A(?:AW|A0|B[123]|C0|D[12])[FPU][0-6](?:-\d{2})?', entry['native_code'])
        assert entry['ros_code'] == 'R' + entry['native_code'][1:]
        if entry['station'].startswith('B'):
            assert entry['station'] == 'B' + str((entry['slot'] - 1) % 3 + 1)
    lower_middle = next(entry for entry in entries if entry['native_code'] == 'AB2P5')
    assert '完整通过' in lower_middle['native_status']
    assert lower_middle['legacy_alias'] == 'demo-2-liaopan-placeto-hongganxiang'


def build(check=False):
    catalog = json.loads((DOCS / 'catalog.json').read_text())
    validate(catalog)
    generated = {
        DOCS / '02-catalog.md': catalog_markdown(catalog['entries']),
        DOCS / '08-evidence.md': evidence_markdown(catalog['entries']),
    }
    nav = ''.join('<a href="#page-{0}">{1}</a>'.format(index, html.escape(title)) for index, (_, title) in enumerate(PAGES))
    sections = []
    for index, (name, title) in enumerate(PAGES):
        path = DOCS / name
        text = generated[path] if path in generated else path.read_text()
        previous = '<span></span>'
        following = '<a href="#page-0">返回首页</a>'
        if index:
            previous = '<a href="#page-{}">← {}</a>'.format(index - 1, html.escape(PAGES[index - 1][1]))
        if index + 1 < len(PAGES):
            following = '<a href="#page-{}">{} →</a>'.format(index + 1, html.escape(PAGES[index + 1][1]))
        sections.append('<article class="page" id="content-{0}" data-route="page-{0}" {1}>{2}<p class="source">文档源 · docs/demo-handbook/{3}</p><div class="pager">{4}{5}</div></article>'.format(index, 'hidden' if index else '', render_markdown(text), html.escape(name), previous, following))
    generated[OUTPUT] = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ARES-R · 功能手册</title><style>' + STYLE + '</style></head><body><header><strong>ARES-R · 功能手册</strong><a href="/demo-console">Demo Console</a><span class="version">v0.1 · 证据截止 2026-11-17</span><button id="print">打印 / PDF</button></header><div class="layout"><aside><label for="search">搜索编号、对象或状态</label><input id="search" type="search" placeholder="例如 RB2P5、筛网、ID3"><div id="searchStatus" aria-live="polite"></div><nav aria-label="手册目录">' + nav + '</nav><p class="note">原生与ROS分别记录。此处为文档快照，实时任务状态见Demo Console。</p></aside><main>' + ''.join(sections) + '</main></div><script>' + SCRIPT + '</script></body></html>\n'
    for path, text in generated.items():
        if check:
            if not path.exists() or path.read_text() != text:
                raise SystemExit('Out of date: ' + str(path))
        else:
            path.write_text(text)
    print('PASS: 20 business capabilities, 6+6 dryer slots, unique codes, links and generated files; {} pages'.format(len(PAGES)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    build(parser.parse_args().check)
