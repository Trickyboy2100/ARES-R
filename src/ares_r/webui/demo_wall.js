/* Capability selection only. Execution stays on the existing Console start API. */
(function (global) {
  'use strict';
  const categories = {F: '取 · Fetch', P: '放 · Place', U: 'Utility', S: '完整流程', T: '测试分支', X: '其他已接入'};

  function resolve(entry, runtime, mode = 'development', transport = 'native') {
    const alias = transport === 'ros' ? entry.ros_launch_alias : entry.launch_alias;
    const demo = alias ? runtime.find(d => d.alias === alias) : null;
    const connected = Boolean(demo && demo.execution_ready !== false);
    const released = transport === 'ros' ? entry.delivery_ros_ready === true : entry.delivery_native_ready === true;
    const runnable = connected && (mode === 'development' || released);
    let reason = entry.launch_note || (demo ? demo.verification_note : '当前后端未注册此功能的独立执行入口。');
    if (transport === 'ros' && !demo) reason = 'ROS网页Action启动桥接待接入；已有Action可按手册调用，原生实机与ROS交付结论分别保留。';
    else if (connected && mode === 'delivery' && !released) reason = '此功能当前开放开发调试；交付模式等待当前参数与完整结果确认。';
    return {demo, runnable, alias, label: runnable ? (transport === 'ros' ? 'ROS入口可用' : '原生入口可用') : connected ? '开发调试' : '待接入', reason};
  }

  function combine(entries, runtime) {
    const known = new Set(entries.map(e => e.legacy_alias).filter(Boolean));
    const extra = runtime.filter(d => !known.has(d.alias)).map(d => ({
      native_code: '', ros_code: '', key: 'runtime:' + d.alias, title: d.title || d.alias,
      category: 'X', station_label: '待归类', station: '', object: '',
      native_status: d.verification_note || '验收范围见运行说明', ros_status: '编号与交付状态待归档',
      legacy_alias: d.alias, launch_alias: d.alias, summary: d.preparation || '', handbook_page: 2,
    }));
    return entries.concat(extra);
  }

  function matches(entry, filters) {
    const text = [entry.native_code, entry.ros_code, entry.title, entry.station, entry.station_label,
      entry.legacy_alias, entry.epic_config, entry.object].join(' ').toLowerCase();
    return (!filters.category || entry.category === filters.category) &&
      (!filters.station || entry.station === filters.station) &&
      (!filters.query || text.includes(filters.query.toLowerCase()));
  }

  const exported = {resolve, combine, matches};
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = exported;
    return;
  }
  global.DemoWall = exported;
  let entries = [], current = null, filters = {category: '', station: '', query: ''};
  let loaded = false, mode = 'delivery', transport = 'native';
  function selectionState(entry) { return resolve(entry, catalog, mode, transport); }
  const byId = id => document.getElementById(id);
  const safe = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

  function view(name) {
    document.body.dataset.consoleView = name;
    document.querySelectorAll('[data-console-view]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.consoleView === name)));
    if (name === 'monitor') requestAnimationFrame(() => paint());
  }

  function drawDetail() {
    const box = byId('wallDetail');
    if (!current) {

    box.innerHTML = '<p>选择一项功能，查看流程、验证记录和启动准备。</p>';
      return;
    }
    const state = selectionState(current);
    const codes = [current.native_code, current.ros_code].filter(Boolean).join(' / ');
    const milestones = (current.milestones || []).map(m => `<span class="milestone ${safe(m.state)}">${safe(m.label)} · ${m.state === 'done' ? '有依据' : m.state === 'review' ? '待核对' : '待完成'}</span>`).join('');
    box.innerHTML = `<div class="wall-detail-heading"><span class="wall-code">${safe(codes)}</span><a href="/demo-handbook#page-${current.handbook_page || 2}" target="_blank" rel="noopener">详细流程与参数 ↗</a></div><h3>${safe(current.title)}</h3><div class="wall-milestones">${milestones}</div><p>${safe(current.summary)}</p><div class="wall-facts"><div><span>原生实机</span>${safe(current.native_status)}</div><div><span>ROS交付</span>${safe(current.ros_status)}</div><div><span>ROS Action</span>${safe(current.ros_action || '待绑定')}</div><div><span>检测模板 / 工位</span>${safe(current.epic_config == null ? '待绑定 / 无5700要求' : 'ID ' + current.epic_config)} · ${safe(current.station_label)}</div><div><span>运行入口</span>${safe(state.demo ? state.demo.alias : '独立入口待接入')}</div></div>${state.demo ? `<details><summary>现有任务的完整准备与版本说明</summary><p>${safe(state.demo.preparation)}</p><p>${safe(state.demo.verification_note)}</p></details>` : ''}<p class="wall-reason">${safe(current.launch_note || (state.demo ? '下方启动按钮调用已部署的原生Console任务。ROS调用方式及交付范围见手册。' : state.reason))}</p>`;
  }

  function select(entry) {
    current = entry;
    const state = selectionState(entry);
    if (state.demo) {
      choose(state.demo.alias);
      capabilityStartAllowed = state.runnable;
      buttons();
      byId('chosen').textContent = [transport === 'ros' ? entry.ros_code : entry.native_code, entry.title].filter(Boolean).join(' · ');
      byId('chosenTags').innerHTML = '<span class="pill">' + (transport === 'ros' ? 'ROS启动' : '原生启动') + '</span><span class="pill">' + safe(categories[entry.category]) + '</span>';
      let preparation = '底盘与双臂静止，当前工具/物体与所选任务一致。';
      if (entry.category === 'P') preparation = '已持有对应物体，底盘位于所选放置工位；5700 ID' + entry.epic_config + ' 可检测目标。';
      if (entry.category === 'T') preparation = '物体位于原抓取夹具，5700 ID' + entry.epic_config + ' 可检测；原位放回测试需保留夹具。';
      byId('preparation').textContent = preparation + ' 任务完整准备条件和参数版本可在右侧展开核对。';
      byId('validation').textContent = '原生实机 · ' + entry.native_status + '；ROS · ' + entry.ros_status;
    } else {
      selected = '';
      capabilityStartAllowed = false;
      byId('ready').checked = false;
      byId('history').checked = false;
      byId('historyAck').hidden = true;
      byId('chosen').textContent = [transport === 'ros' ? entry.ros_code : entry.native_code, entry.title].filter(Boolean).join(' · ');
      byId('chosenTags').innerHTML = '<span class="pill">待接入</span>';
      byId('preparation').textContent = entry.launch_note || '当前功能可查看定义、证据和待办，独立执行入口尚待接入。';
      byId('validation').textContent = entry.native_status + ' · ' + entry.ros_status;
      buttons();
    }
    byId('message').textContent = state.runnable ? '已选择现有入口；完成准备确认后可运行一次。' : state.reason;
    byId('wallEditor').hidden = mode !== 'development';
    if (mode === 'development') loadDraft(entry);
    draw();
  }

  function draw() {
    if (!loaded) return;
    const all = combine(entries, catalog);
    const visible = all.filter(e => matches(e, filters));
    byId('wallCount').textContent = visible.length + ' / ' + all.length + ' 项功能';
    byId('wallGrid').innerHTML = Object.entries(categories).map(([category, label]) => {
      const rows = visible.filter(e => e.category === category);
      if (!rows.length) return '';
      return `<section class="wall-group"><h2>${label}<span>${rows.length}</span></h2><div class="wall-tiles">` + rows.map(e => {
        const state = selectionState(e);
        const key = e.native_code || e.key;
        const active = current && (current.native_code || current.key) === key;
        return `<button type="button" class="wall-tile ${state.runnable ? '' : 'is-unavailable'} ${active ? 'is-selected' : ''}" data-wall-key="${safe(key)}" aria-pressed="${active}"><span class="wall-tile-top"><span class="wall-code">${safe((transport === 'ros' ? e.ros_code : e.native_code) || '待编号')}</span><span class="wall-status ${state.runnable ? 'is-connected' : ''}">${state.label}</span></span><strong>${safe(e.title)}</strong><span class="wall-station">${safe(e.station_label)} · ${safe(e.object)}</span><span class="wall-flow">${safe(e.summary)}</span><span class="wall-evidence"><b>实机</b>${safe(e.native_status)}</span><span class="wall-evidence"><b>ROS</b>${safe(e.ros_status)}</span><span class="wall-ros-code">${safe(e.ros_code || '')}</span></button>`;
      }).join('') + '</div></section>';
    }).join('') || '<p class="wall-empty">没有匹配功能，可清除搜索或切换分类。</p>';
    byId('wallGrid').querySelectorAll('[data-wall-key]').forEach(button => {
      button.onclick = () => select(all.find(e => (e.native_code || e.key) === button.dataset.wallKey));
    });
    drawDetail();
  }

  async function initialize() {
    try {
      const response = await fetch('/api/demo-console/capabilities');
      if (!response.ok) throw Error('HTTP ' + response.status);
      const data = await response.json();
      entries = data.entries;
      if (!Array.isArray(entries)) throw Error('功能目录格式错误');
      loaded = true;
      byId('wallRevision').textContent = '目录 ' + data.revision + ' · 原生状态与ROS状态分别记录';
      byId('wallCategory').innerHTML = '<option value="">全部功能</option>' + Object.entries(categories).map(([key, label]) => `<option value="${key}">${label}</option>`).join('');
      const stations = new Map(entries.map(e => [e.station, e.station_label]));
      byId('wallStation').innerHTML = '<option value="">全部工位</option>' + [...stations].map(([key, label]) => `<option value="${safe(key)}">${safe(key)} · ${safe(label)}</option>`).join('');
      draw();
    } catch (error) {
      byId('wallRevision').textContent = '功能目录读取失败 · ' + error.message;
      byId('wallGrid').innerHTML = '<p class="wall-empty">目录暂不可用。可切换运行监控查看后端已有入口。</p>';
    }
  }

  function loadDraft(entry) {
    const key = 'ares-function-draft:' + (entry.native_code || entry.key);
    const initial = {schema_version: 1, capability_code: entry.native_code || entry.key,
      title: entry.title, epic_config: entry.epic_config ?? null, parameter_changes: {},
      debug_notes: '', stage: 'DRAFT', effective_in_runtime: false};
    let saved;
    try { saved = localStorage.getItem(key); } catch (_) { /* Browser storage may be disabled. */ }
    byId('wallDraft').value = saved || JSON.stringify(initial, null, 2);
    byId('wallDraftStatus').textContent = saved ? '已读取本机草稿' : '新草稿，修改后保存或导出';
  }
  function readDraft() {
    if (!current) throw Error('先选择功能');
    const draft = JSON.parse(byId('wallDraft').value);
    if (draft.capability_code !== (current.native_code || current.key)) throw Error('草稿编号与当前功能不一致');
    draft.effective_in_runtime = false;
    return draft;
  }
  byId('wallSaveDraft').onclick = () => {
    try {
      const draft = readDraft();
      localStorage.setItem('ares-function-draft:' + draft.capability_code, JSON.stringify(draft, null, 2));
      byId('wallDraftStatus').textContent = '草稿已保存到当前浏览器';
    } catch (error) { byId('wallDraftStatus').textContent = error.message; }
  };
  byId('wallExportDraft').onclick = () => {
    try {
      const draft = readDraft();
      const url = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], {type: 'application/json'}));
      const link = document.createElement('a'); link.href = url;
      link.download = draft.capability_code.replace(/[^a-zA-Z0-9_-]/g, '_') + '-draft.json';link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { byId('wallDraftStatus').textContent = error.message; }
  };
  function changeMode() {
    mode = byId('wallMode').value; transport = byId('wallTransport').value;
    document.body.dataset.consoleMode = mode;
    capabilityStartAllowed = false; selected = ''; byId('ready').checked = false; buttons();
    byId('wallModeNote').textContent = mode === 'delivery' ? '交付模式 · 已确认当前可用入口可启动，其余功能保留灰色卡片。' : '开发模式 · 调试已接入候选功能，编辑与导出本机草稿。';
    byId('wallEditor').hidden = mode !== 'development';
    if (current) select(current); else draw();
  }
  byId('wallMode').onchange = changeMode;
  byId('wallTransport').onchange = changeMode;
  document.querySelectorAll('[data-console-view]').forEach(button => button.onclick = () => view(button.dataset.consoleView));
  byId('wallSearch').oninput = event => { filters.query = event.target.value.trim(); draw(); };
  byId('wallCategory').onchange = event => { filters.category = event.target.value; draw(); };
  byId('wallStation').onchange = event => { filters.station = event.target.value; draw(); };
  byId('wallClear').onclick = () => {
    filters = {category: '', station: '', query: ''};
    byId('wallSearch').value = ''; byId('wallCategory').value = ''; byId('wallStation').value = ''; draw();
  };
  global.addEventListener('demo-catalog-loaded', draw);
  global.addEventListener('demo-started', () => view('monitor'));
  // Selecting a legacy list item clears an unrelated wall selection.
  global.addEventListener('demo-legacy-selected', event => {
    if (current && selectionState(current).alias !== event.detail.alias) { current = null; draw(); }
    const entry = combine(entries, catalog).find(e => (transport === 'ros' ? e.ros_launch_alias : e.launch_alias) === event.detail.alias);
    capabilityStartAllowed = Boolean(entry && selectionState(entry).runnable);
  });
  document.body.dataset.consoleMode = mode;
  view('wall');
  initialize();
})(typeof window === 'undefined' ? globalThis : window);
