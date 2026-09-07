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
    scene=json.loads(path.read_text()).get("demo")
    data = json.dumps(dict(q=q, dt=dt, series=[delta, velocity, acceleration], info=info,scene=scene)).replace("<", "\\u003c")
    html = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>ARES-R cuRobo 轨迹预览</title><style>
body{font:16px system-ui;background:#10202e;color:#e0edf4;max-width:1100px;margin:28px auto;padding:0 20px}
canvas{background:#192e40;width:100%;border-radius:10px;margin:8px 0}button,input{margin:10px;font-size:16px}
.warn{color:#ffd16d}table{width:100%;text-align:center}pre{white-space:pre-wrap}
</style><h1>ARES-R · cuRobo 点到点轨迹</h1>
<p class="warn">离线数据回放，无机器人控制连接。曲线不代表已认证避障或实机跟踪结果。</p>
<button id="play">播放 / 暂停预览</button><input id="seek" type="range" min="0" value="0" style="width:65%">
<div id="time"></div><table><thead><tr><th>J1 °</th><th>J2 °</th><th>J3 °</th><th>J4 °</th><th>J5 °</th><th>J6 °</th></tr></thead><tbody id="angles"></tbody></table>
<canvas id="scene" width="1000" height="640" style="display:none"></canvas>
<canvas id="c0" width="1000" height="230"></canvas><canvas id="c1" width="1000" height="230"></canvas><canvas id="c2" width="1000" height="230"></canvas>
<p>速度/加速度为采样点有限差分；图末端未绘制回到静止的额外差分段，数值安全检查包含该段。</p><pre id="summary"></pre>
<script>const data=__DATA__;
const colors=['#67dcff','#ff7d86','#c3a1ff','#ffc967','#8fe59b','#ff99e3'];
const seek=document.getElementById('seek');seek.max=data.q.length-1;
document.getElementById('summary').textContent=JSON.stringify(data.info,null,2);
function draw(){const k=Number(seek.value);document.getElementById('time').textContent='t = '+(k*data.dt).toFixed(3)+' s / '+data.info.duration_s.toFixed(3)+' s';
document.getElementById('angles').innerHTML='<tr>'+data.q[k].map((v,j)=>'<td style="color:'+colors[j]+'">'+v.toFixed(5)+'</td>').join('')+'</tr>';drawScene(k);
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
    scene_js="""
function drawScene(k){if(!data.scene||!data.scene.world_obstacle_corners_m)return;
const c=document.getElementById('scene');c.style.display='block';const ctx=c.getContext('2d');ctx.clearRect(0,0,1000,640);
const frames=data.scene.world_link_points_m,box=data.scene.world_obstacle_corners_m,cloud=frames.flat().concat(box);
const views=[['3D / body frame',p=>[.7*p[0]-.7*p[1],p[2]+.25*(p[0]+p[1])]],['TOP (-Y, X)',p=>[-p[1],p[0]]],['REAR (-Y, Z)',p=>[-p[1],p[2]]],['RIGHT (X, Z)',p=>[p[0],p[2]]]];
views.forEach(([title,proj],v)=>{const ox=(v%2)*500,oy=Math.floor(v/2)*320,xy=cloud.map(proj);
const minX=Math.min(...xy.map(p=>p[0])),maxX=Math.max(...xy.map(p=>p[0])),minY=Math.min(...xy.map(p=>p[1])),maxY=Math.max(...xy.map(p=>p[1]));
const scale=Math.min(400/Math.max(.1,maxX-minX),225/Math.max(.1,maxY-minY));
function point(p){const a=proj(p);return [ox+70+(a[0]-minX)*scale,oy+275-(a[1]-minY)*scale]}
function line(a,b,color,width=2){a=point(a);b=point(b);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke()}
ctx.fillStyle='#e0edf4';ctx.font='13px monospace';ctx.fillText(title,ox+15,oy+20);
for(let i=0;i<5;i++){let x=minX+(maxX-minX)*i/4,y=minY+(maxY-minY)*i/4;ctx.fillText(x.toFixed(2),ox+70+(x-minX)*scale,oy+299);ctx.fillText(y.toFixed(2),ox+12,oy+275-(y-minY)*scale)}
for(let i=1;i<frames.length;i++)line(frames[i-1][7],frames[i][7],'#8fe59b',2);
if(box.length===8)for(let i=0;i<8;i++)for(let b of [1,2,4])if((i^b)>i)line(box[i],box[i^b],'#ff7d86',3);
const joints=frames[k];for(let i=1;i<joints.length;i++)line(joints[i-1],joints[i],'#67dcff',4);
joints.forEach((p,i)=>{const a=point(p);ctx.fillStyle=i===7?'#ffc967':'#fff';ctx.beginPath();ctx.arc(...a,i===7?6:4,0,Math.PI*2);ctx.fill();ctx.fillText(i===7?'TCP':String(i),a[0]+6,a[1]-5)});
});ctx.fillStyle='#ffd16d';ctx.fillText('Virtual obstacle / planned TCP path only; body coordinates in meters',15,635)}
"""
    html=html.replace("</script>",scene_js+"</script>")
    output = path.with_suffix(".preview.html")
    output.write_text(html, encoding="utf-8")
    return output
