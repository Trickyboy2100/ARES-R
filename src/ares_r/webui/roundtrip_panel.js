(() => {
  const panel=document.createElement('section');panel.className='card';panel.id='roundtripPanel';
  panel.style.cssText='padding:14px;border:1px solid #79c9ff;border-radius:10px;margin:8px 0 18px;background:#122333';
  panel.innerHTML=`<h3>完整抓放 Demo</h3><label>运行模式 <select id="roundtripMode"><option value="SITE">现场监督执行</option><option value="SYNTHETIC_GPU_REPLAY">离线 GPU 回放（合成设备）</option></select></label>
    <p style="font-size:13px">ID1抓取 → 水平抬升230mm → 底盘到PLACE → ID3＋下层中间偏置＋40mm → 松爪 → 不收臂原路返回。</p>
    <p style="font-size:12px;color:#ffcc80">首次全链联调，尚未完成实机commissioning。每段规划最多3次：FAST 4秒 → QUALITY → QUALITY。</p>
    <label style="display:flex;gap:8px;align-items:flex-start"><input id="roundtripOnsite" type="checkbox" style="width:auto;margin-top:4px">
      <span>现场有人持续监控、物理急停可用；已确认双臂保持当前/释放后姿态时的完整底盘扫掠净空及上方40mm释放方式。</span></label>
    <button id="roundtripStart" disabled style="background:#1c684f;margin-top:12px">一键开始完整抓放（实机）</button>
    <button id="roundtripResume" disabled>从已验证断点恢复</button>
    <button id="roundtripStop" class="stop" style="margin-top:8px">停止完整流程</button>
    <p id="roundtripState" aria-live="polite">正在读取后台状态…</p>
    <p id="roundtripError" style="color:#ffb6b6;white-space:pre-wrap" aria-live="assertive"></p>
    <details><summary>当前阶段 / 参数 / 日志</summary><pre id="roundtripDetail" style="max-height:240px;overflow:auto;white-space:pre-wrap;word-break:break-all"></pre></details>
    <p style="font-size:12px;color:#b7c2cd">只在点击启动后运行；刷新/开机不自动启动。启动后关闭网页不会停止后台流程，请用STOP停止；软件停止不能替代物理急停。</p>`;
  const container=document.querySelector('aside.right')||document.querySelector('main');
  if(!container)return;container.prepend(panel);
  const find=id=>document.getElementById(id);
  const checkbox=find('roundtripOnsite'),start=find('roundtripStart'),stop=find('roundtripStop');
  let current=null,pending=false,lastDigest=null;
  async function call(path,body){
    const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const value=await response.json();if(!response.ok)throw Error(value.error||response.status);return value;
  }
  function paint(value){
    current=value;
    find("roundtripResume").disabled=pending||value.running||!value.can_resume;
    if(lastDigest&&lastDigest!==value.contract_sha256)checkbox.checked=false;
    lastDigest=value.contract_sha256;
    const stage=value.current_event;
    find('roundtripState').textContent=`${value.run_id||""} · ${value.state} · ${stage?stage.stage+' / '+stage.state:'等待现场确认'}${value.elapsed_s==null?'':' · '+value.elapsed_s.toFixed(1)+'秒'}`;
    find('roundtripDetail').textContent=JSON.stringify({revision:value.revision,stage_count:value.stage_count,
      parameters:value.parameters,slot_offset_m_rad:value.slot_offset_m_rad,events:value.recent_events,
      run_dir:value.run_dir,log:value.log},null,2);
    if(value.blockers.length)find('roundtripError').textContent=value.blockers.join('\n');
    else if(value.failure_message)find('roundtripError').textContent=value.failure_message;
    start.disabled=pending||value.running||(find("roundtripMode").value==="SITE"&&(!value.can_start||!checkbox.checked));
    checkbox.disabled=pending||value.running;
    if(value.running)checkbox.checked=false;
  }
  async function refresh(){try{paint(await call('/api/demo/roundtrip/status'));}
    catch(error){start.disabled=true;find('roundtripError').textContent='后台状态不可用：'+error.message;}}
  checkbox.addEventListener('change',()=>{if(current)paint(current);});
  start.addEventListener('click',async()=>{
    if(pending||!current||current.running||(find("roundtripMode").value==="SITE"&&!checkbox.checked))return;
    pending=true;start.disabled=true;checkbox.disabled=true;find('roundtripError').textContent='';
    try{paint(await call('/api/demo/roundtrip/start',{authorization:'RIGHT GRASP PLACE ROUNDTRIP',
      onsite_observer_confirmed:checkbox.checked,execution_mode:find('roundtripMode').value,contract_sha256:current.contract_sha256}));checkbox.checked=false;}
    catch(error){find('roundtripError').textContent='未启动：'+error.message;}
    finally{pending=false;await refresh();}
  });
  find('roundtripMode').addEventListener('change',()=>{if(current)paint(current);});
  find('roundtripResume').addEventListener('click',async()=>{
    if(!current||pending)return;pending=true;
    try{await call('/api/demo/roundtrip/resume',{run_id:current.run_id,authorization:'RIGHT GRASP PLACE ROUNDTRIP',onsite_observer_confirmed:checkbox.checked});}
    catch(error){find('roundtripError').textContent=error.message;}
    finally{pending=false;await refresh();}
  });
  stop.addEventListener('click',async()=>{
    try{await call('/api/demo/roundtrip/stop',{});checkbox.checked=false;
      find('roundtripError').textContent='已请求停止；不会自动重试或恢复。物理急停独立有效。';await refresh();}
    catch(error){find('roundtripError').textContent='停止请求失败，请使用现场急停：'+error.message;}
  });
  refresh();setInterval(refresh,1500);
})();
