(() => {
  const panel=document.createElement('section');panel.className='card';panel.id='roundtripPanel';
  panel.style.cssText='padding:14px;border:1px solid #79c9ff;border-radius:10px;margin:8px 0 18px;background:#122333';
  panel.innerHTML=`<h3>完整抓放 Demo</h3><label>运行模式 <select id="roundtripMode"><option value="SITE">现场监督执行</option><option value="SYNTHETIC_GPU_REPLAY">离线 GPU 回放（合成设备）</option></select></label>
    <p id="roundtripRuntime" style="font-size:12px;overflow-wrap:anywhere">正在核对部署版本…</p>
    <p style="font-size:13px">空爪center → ID1抓取 → 连续水平抬升230mm（一次ServoJ，中途不停） → 底盘40/81/32cm到PLACE → ID3＋下层中间偏置＋40mm → 连续下降50mm → 松爪 → 不收臂，底盘32/81/40cm返回。</p>
    <fieldset><legend>完整Demo全程 TCP任务偏置 · BODY</legend>
      <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px">${['dX / mm','dY / mm','dZ / mm','dRoll / °','dPitch / °','dYaw / °'].map((label,i)=>`<label>${label}<input id="roundtripOffset${i}" type="number" value="0" step="0.1" style="width:100%;box-sizing:border-box"></label>`).join('')}</div>
      <button id="roundtripSaveOffset">保存任务偏置</button><button id="roundtripZeroOffset">填入全零</button>
      <p style="font-size:12px">只修正任务目标，不修改控制器TCP标定；XYZ沿BODY轴，旋转按BODY固定轴XYZ。相对抬升/下降不重复叠加偏置。非零Roll/Pitch仍须通过水平约束验证。</p>
    </fieldset>
    <p style="font-size:12px;color:#ffcc80">放置定义：+40mm预放置后下降50mm，最终TCP在泊位参考点下方10mm。新下降段尚未实机commission。</p>
    <p id="roundtripPlanningPolicy" style="font-size:12px;color:#ffcc80">首次全链联调，尚未完成实机commissioning。正在读取规划期限…</p>
    <p id="roundtripRoute" style="font-size:12px"></p>
    <p id="roundtripLiftPolicy" style="font-size:12px;color:#ffcc80"></p>
    <p id="roundtripCompensation" style="font-size:12px;color:#9ee4c2"></p>
    <p id="roundtripCachePolicy" style="font-size:12px"></p>
    <label style="display:flex;gap:8px;align-items:flex-start"><input id="roundtripOnsite" type="checkbox" style="width:auto;margin-top:4px">
      <span>现场有人持续监控、物理急停可用；已确认持物/释放姿态的底盘扫掠净空，以及预放置后下降50mm再释放的空间。</span></label>
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
  let current=null,pending=false,lastDigest=null,offsetDirty=false;
  async function call(path,body){
    const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const value=await response.json();if(!response.ok)throw Error(value.error||response.status);return value;
  }
  function paint(value){
    current=value;
    const offset=value.parameters?.task_tcp_offset_m_rad||[0,0,0,0,0,0];
    for(let i=0;i<6;i++){
      const input=find('roundtripOffset'+i);input.disabled=!!value.running||pending;
      if(!offsetDirty)input.value=String(offset[i]*(i<3?1000:180/Math.PI));
    }
    find('roundtripSaveOffset').disabled=pending||!!value.running;
    find('roundtripZeroOffset').disabled=pending||!!value.running;
    const deadline=value.parameters?.planning_deadline_s;
    find('roundtripLiftPolicy').textContent=value.parameters?.lift_execution_mode==='CONTINUOUS230'
      ?'连续230mm抬升：一份轨迹、一次Servo启停，100mm处不停顿；新抬升尚未实机commission。'+(value.parameters?.lift_lower_fixture_contact_escape?.enabled?' 本Demo仅允许已确认的下方抓取泊位接触后向上脱离，连杆/其他障碍检查保留。':'')
      :'历史两段抬升模式。';
    const comp=value.parameters?.demo_tcp_orientation_compensation;
    find('roundtripCompensation').textContent=comp?.enabled
      ?`本Demo全程临时姿态补偿：${comp.axis} ${comp.angle_deg}°；缓存已含补偿，不重复叠加；不修改检测数据或工具标定。`:'本Demo临时姿态补偿未启用。';
    find('roundtripCachePolicy').textContent=value.parameters?.pregrasp_cache?.enabled
      ?'center→预抓取优先复用已缓存cuRobo轨迹；fresh观测核对目标、实际起点及新场景；不匹配则使用新场景重新cuRobo规划，不放宽目标误差。'
      :'预抓取使用fresh cuRobo求解。';
    find('roundtripPlanningPolicy').textContent=`首次全链联调，尚未完成实机commissioning。每段规划最多3次：FAST ${deadline==null?'未知':deadline}秒 → QUALITY → QUALITY。`;
    find('roundtripRuntime').textContent=`版本：${value.revision||'未知'} ｜目录：${value.runtime_binding?.repository_root||'未知'}`;
    const legs=value.base_route_body_m;
    find('roundtripRoute').textContent=legs?`底盘六段 BODY 位移（米）：${JSON.stringify(legs)}`:'底盘路线尚未读取';
    find("roundtripResume").disabled=pending||value.running||!value.can_resume;
    if(lastDigest&&lastDigest!==value.contract_sha256)checkbox.checked=false;
    lastDigest=value.contract_sha256;
    const stage=value.current_event;
    const source=value.execution_mode==='SYNTHETIC_GPU_REPLAY'?'历史离线回放（非实机）':'实机流程';
    find('roundtripState').textContent=`${source} · ${value.run_id||""} · ${value.state} · ${stage?stage.stage+' / '+stage.state:'等待现场确认'}${value.elapsed_s==null?'':' · '+value.elapsed_s.toFixed(1)+'秒'}`;
    find('roundtripDetail').textContent=JSON.stringify({revision:value.revision,stage_count:value.stage_count,
      parameters:value.parameters,slot_offset_m_rad:value.slot_offset_m_rad,events:value.recent_events,
      runtime_binding:value.runtime_binding,base_route_body_m:value.base_route_body_m,
      run_dir:value.run_dir,log:value.log},null,2);
    if((value.blockers||[]).length)find('roundtripError').textContent=value.blockers.join('\n');
    else if(value.failure_message)find('roundtripError').textContent=value.failure_message;
    start.textContent=find('roundtripMode').value==='SITE'?'一键开始完整抓放（实机）':'一键开始完整GPU离线回放';
    start.disabled=pending||offsetDirty||value.running||(find("roundtripMode").value==="SITE"&&(!value.can_start||!checkbox.checked));
    checkbox.disabled=pending||value.running;
    if(value.running)checkbox.checked=false;
  }
  async function refresh(){try{paint(await call('/api/demo/roundtrip/status'));}
    catch(error){start.disabled=true;find('roundtripError').textContent='后台状态不可用：'+error.message;}}
  checkbox.addEventListener('change',()=>{if(current)paint(current);});
  for(let i=0;i<6;i++)find('roundtripOffset'+i).addEventListener('input',()=>{
    offsetDirty=true;checkbox.checked=false;if(current)paint(current);
  });
  find('roundtripZeroOffset').addEventListener('click',()=>{
    for(let i=0;i<6;i++)find('roundtripOffset'+i).value='0';offsetDirty=true;checkbox.checked=false;if(current)paint(current);
  });
  find('roundtripSaveOffset').addEventListener('click',async()=>{
    if(!current||current.running||pending)return;
    const values=Array.from({length:6},(_,i)=>find('roundtripOffset'+i).value.trim()===''?NaN:Number(find('roundtripOffset'+i).value)*(i<3?.001:Math.PI/180));
    if(!values.every(Number.isFinite)){find('roundtripError').textContent='六个偏置必须为有限数值';return;}
    pending=true;
    try{
      await call('/api/demo/roundtrip/settings',{contract_sha256:current.contract_sha256,task_tcp_offset_m_rad:values});
      offsetDirty=false;checkbox.checked=false;find('roundtripError').textContent='偏置已保存；只对下一次任务生效，未发送运动。';
    }catch(error){find('roundtripError').textContent='保存失败：'+error.message;}
    finally{pending=false;await refresh();}
  });
  start.addEventListener('click',async()=>{
    if(pending||offsetDirty||!current||current.running||(find("roundtripMode").value==="SITE"&&!checkbox.checked))return;
    pending=true;start.disabled=true;checkbox.disabled=true;find('roundtripError').textContent='';
    try{await call('/api/demo/roundtrip/start',{authorization:'RIGHT GRASP PLACE ROUNDTRIP',
      onsite_observer_confirmed:checkbox.checked,execution_mode:find('roundtripMode').value,contract_sha256:current.contract_sha256});checkbox.checked=false;}
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
