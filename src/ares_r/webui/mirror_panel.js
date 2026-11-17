(() => {
  const host = document.querySelector('#mirrorTools') || document.querySelector('#manual') || document.querySelector('aside.right') ||
    document.querySelector('#catalog')?.parentElement;
  if (!host) return;
  const panel = document.createElement('section');
  panel.className = 'card';
  panel.style.cssText = 'padding:14px;border:1px solid #35526a;border-radius:8px;margin:12px 0';
  panel.innerHTML = `<h3>双臂关节点镜像</h3>
    <p>以 BODY Y=0 为对称面，点击后求解、检查路径并执行目标臂运动。</p>
    <label><input type="checkbox" data-match-tcp checked>同时镜像 TCP 位置和朝向</label>
    <p>启用时优先匹配 TCP，腕部可微调；关闭则保留原关节点镜像。工具标定不变。</p>
    <small>TCP +X、+Z 按 BODY 左右对称；+Y 保持右手坐标系。到位后回读位置和朝向。</small>
    <button data-destination="left">左臂镜像右臂 · 移动左臂</button>
    <button data-destination="right">右臂镜像左臂 · 移动右臂</button>
    <button data-stop>停止镜像运动</button>
    <p data-chassis>正在读取车体几何策略…</p>
    <p data-status role="status">准备就绪</p>
    <details><summary>目标、关节点误差与执行记录</summary><pre data-detail></pre></details>`;
  host.prepend(panel);
  const buttons = [...panel.querySelectorAll('[data-destination]')];
  const text = panel.querySelector('[data-status]');
  const detail = panel.querySelector('[data-detail]');
  let pending = false;
  const stages = {SOLVING: '求解镜像关节点', CHECKING_PATH: '检查运动路径',
    EXECUTING: 'JAKA 执行中', COMPLETED: '已到位', FAULT: '失败'};
  async function api(path, body) {
    const response = await fetch(path, body === undefined ? {} : {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) throw Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  async function refresh() {
    try {
      const status = await api('/api/operations/run-status');
      buttons.forEach(button => button.disabled = pending || status.state === 'RUNNING');
      if (status.mode !== 'JOINT_MIRROR' || pending) return;
      const mirror = status.mirror || {};
      const stage = stages[mirror.stage] || status.state;
      const reason = mirror.error || status.failure_reason || '';
      const failure = status.failure_summary;
      text.textContent = `${stage} · ${status.destination_arm === 'left' ? '左臂镜像右臂' : '右臂镜像左臂'}` +
        ` · ${Number(status.elapsed_s || 0).toFixed(1)} 秒` +
        (failure ? ` · ${failure.title}。${failure.action}` : reason ? ` · ${reason.slice(0, 160)}` : '');
      const plan = mirror.plan;
      const result = status.execution_result;
      if (plan?.tcp_target_body) {
        text.textContent += ` · TCP ${result?.tcp_mirror_verified ? '已回读验证' : '匹配模式'}`;
        if (result?.tcp_position_error_mm !== undefined)
          text.textContent += ` · ${Number(result.tcp_position_error_mm).toFixed(2)} mm / ${Number(result.tcp_orientation_error_deg).toFixed(2)}°`;
      }
      detail.textContent = JSON.stringify({plan, result,
        output: status.output, error: reason || undefined}, null, 2);
    } catch (error) {
      if (!pending) text.textContent = `状态读取失败 · ${error.message}`;
    }
  }
  buttons.forEach(button => button.onclick = async () => {
    pending = true;
    buttons.forEach(item => item.disabled = true);
    const destination = button.dataset.destination;
    const source = destination === 'left' ? 'right' : 'left';
    text.textContent = '正在读取状态并准备镜像任务…';
    try {
      await api('/api/operations/mirror', {source_arm: source, destination_arm: destination,
        match_tcp: panel.querySelector('[data-match-tcp]').checked,
        authorization: `MIRROR ${destination.toUpperCase()} FROM ${source.toUpperCase()}`,
        command_id: `mirror-${Date.now()}-${Math.random().toString(16).slice(2)}`});
      text.textContent = '镜像任务已启动';
    } catch (error) {
      text.textContent = `未启动 · ${error.message}`;
    } finally {
      pending = false;
      await refresh();
    }
  });
  panel.querySelector('[data-stop]').onclick = async () => {
    try {
      await api('/api/operations/stop', {});
      text.textContent = '已请求停止，正在确认执行器退出';
    } catch (error) { text.textContent = error.message; }
  };
  setInterval(refresh, 1500);
  api('/api/system/status').then(status => {
    const enabled = status.system_info?.geometry_policy?.chassis_collision_enabled;
    const version = status.system_info?.webui_build_version || '版本未知';
    const chassis = enabled === false ? '车体模型 · 全局禁用' :
      enabled === true ? '车体模型 · 启用' : '车体模型状态未知';
    panel.querySelector('[data-chassis]').textContent = `${version} · ${chassis}`;
  }).catch(error => { panel.querySelector('[data-chassis]').textContent = error.message; });
  refresh();
})();
