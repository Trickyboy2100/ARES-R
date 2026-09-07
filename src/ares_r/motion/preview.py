"""Self-contained offline trajectory plot; no network or control callbacks."""

import json
import math
from pathlib import Path

from .trajectory import load_trajectory
from .curobo import summarize


def write_preview(path):
    path = Path(path)
    trajectory = load_trajectory(path)
    info = summarize(trajectory.points, trajectory.sample_period_s)
    dt = trajectory.sample_period_s
    q = [[math.degrees(v) for v in point] for point in trajectory.points]
    delta = [[p[j]-q[0][j] for j in range(6)] for p in q]
    velocity = [[0.0]*6] + [[(b[j]-a[j])/dt for j in range(6)] for a,b in zip(q,q[1:])]
    acceleration = [[0.0]*6] + [[(b[j]-a[j])/dt for j in range(6)] for a,b in zip(velocity,velocity[1:])]
    data = json.dumps(dict(q=q, dt=dt, series=[delta, velocity, acceleration], info=info)).replace("<", "\\u003c")
    html = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>ARES-R cuRobo 轨迹预览</title><style>
body{font:16px system-ui;background:#10202e;color:#e0edf4;max-width:1100px;margin:28px auto;padding:0 20px}
canvas{background:#192e40;width:100%;border-radius:10px;margin:8px 0}button,input{margin:10px;font-size:16px}
.warn{color:#ffd16d}table{width:100%;text-align:center}pre{white-space:pre-wrap}
</style><h1>ARES-R · cuRobo 点到点轨迹</h1>
<p class="warn">离线数据回放，无机器人控制连接。曲线不代表已认证避障或实机跟踪结果。</p>
<button id="play">播放 / 暂停预览</button><input id="seek" type="range" min="0" value="0" style="width:65%">
<div id="time"></div><table><thead><tr><th>J1 °</th><th>J2 °</th><th>J3 °</th><th>J4 °</th><th>J5 °</th><th>J6 °</th></tr></thead><tbody id="angles"></tbody></table>
<canvas id="c0" width="1000" height="230"></canvas><canvas id="c1" width="1000" height="230"></canvas><canvas id="c2" width="1000" height="230"></canvas>
<p>速度/加速度为采样点有限差分；图末端未绘制回到静止的额外差分段，数值安全检查包含该段。</p><pre id="summary"></pre>
<script>const data=__DATA__;
const colors=['#67dcff','#ff7d86','#c3a1ff','#ffc967','#8fe59b','#ff99e3'];
const seek=document.getElementById('seek');seek.max=data.q.length-1;
document.getElementById('summary').textContent=JSON.stringify(data.info,null,2);
function draw(){const k=Number(seek.value);document.getElementById('time').textContent='t = '+(k*data.dt).toFixed(3)+' s / '+data.info.duration_s.toFixed(3)+' s';
document.getElementById('angles').innerHTML='<tr>'+data.q[k].map((v,j)=>'<td style="color:'+colors[j]+'">'+v.toFixed(5)+'</td>').join('')+'</tr>';
data.series.forEach((rows,index)=>{const ctx=document.getElementById('c'+index).getContext('2d');ctx.clearRect(0,0,1000,230);
let scale=0.00001;rows.forEach(p=>p.forEach(v=>scale=Math.max(scale,Math.abs(v))));scale*=1.1;
ctx.fillStyle='#e0edf4';ctx.font='14px monospace';ctx.fillText(['关节偏移 Δq (°)','有限差分速度 (°/s)','有限差分加速度 (°/s²)'][index],12,20);
for(let tick=0;tick<=4;tick++){let y=40+tick*40;ctx.strokeStyle='#344e62';ctx.beginPath();ctx.moveTo(90,y);ctx.lineTo(980,y);ctx.stroke();ctx.fillText((scale*(1-tick/2)).toFixed(5),8,y+4);}
for(let j=0;j<6;j++){ctx.strokeStyle=colors[j];ctx.beginPath();rows.forEach((p,i)=>{let x=90+890*i/(rows.length-1),y=120-p[j]/scale*80;i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();}
ctx.strokeStyle='#fff';ctx.beginPath();let x=90+890*k/(rows.length-1);ctx.moveTo(x,35);ctx.lineTo(x,200);ctx.stroke();ctx.fillText('0 s',90,222);ctx.fillText(data.info.duration_s.toFixed(3)+' s',895,222);});}
seek.oninput=draw;let playing=false,last=0,elapsed=0;
document.getElementById('play').onclick=()=>{playing=!playing;last=0;elapsed=Number(seek.value)*data.dt;if(playing&&Number(seek.value)==data.q.length-1){seek.value=0;elapsed=0;}};
function animate(t){if(playing){if(last)elapsed+=(t-last)/1000;seek.value=Math.min(data.q.length-1,Math.floor(elapsed/data.dt));draw();if(Number(seek.value)==data.q.length-1)playing=false;}last=t;requestAnimationFrame(animate)}draw();requestAnimationFrame(animate);
</script></html>""".replace("__DATA__", data)
    output = path.with_suffix(".preview.html")
    output.write_text(html, encoding="utf-8")
    return output
