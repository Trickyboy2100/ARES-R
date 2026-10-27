// Uses exact repository HTML/JS with route-fulfilled local API fixtures.
// Chromium issues no real network requests and cannot reach device adapters.
const fs=require('fs'),path=require('path');
const {chromium}=require(process.env.ARES_PLAYWRIGHT || 'playwright');
(async()=>{
 const root=process.cwd(), priv=process.argv[2],out=process.argv[3];const fixture=JSON.parse(fs.readFileSync(path.join(priv,'ui_fixture.json')));fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:process.env.CHROME_BIN||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage']});const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1.5,serviceWorkers:'block'});let failures=[],requests=[];page.on('pageerror',e=>failures.push(e.message));
 await page.route('**/*',async route=>{let u=new URL(route.request().url()),p=u.pathname;requests.push({path:p,method:route.request().method()});
 if(u.hostname!=='ares-offline.invalid')return route.abort();
 let files={'/':'src/ares_r/webui/index.html','/workbench':'src/ares_r/webui/workbench.html','/static/roundtrip-panel.js':'src/ares_r/webui/roundtrip_panel.js'};
 if(files[p])return route.fulfill({status:200,contentType:p.endsWith('.js')?'text/javascript':'text/html',body:fs.readFileSync(path.join(root,files[p]))});
 if(Object.hasOwn(fixture,p))return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(fixture[p])});
 return route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({error:'OFFLINE_ROUTE_DENIED'})});});
 await page.goto('http://ares-offline.invalid/');await page.waitForTimeout(1100);await page.evaluate(()=>{yaw=20*Math.PI/180;pitch=-24*Math.PI/180;draw()});await page.screenshot({path:path.join(out,'webui_scene3d.png')});
 await page.evaluate(()=>openStudio());await page.waitForTimeout(500);await page.screenshot({path:path.join(out,'webui_skill_palette.png')});await page.evaluate(()=>selectNode(3));await page.screenshot({path:path.join(out,'webui_scheme_builder.png')});await page.locator('#runMonitor').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'webui_stop_fault_log.png')});
 await page.goto('http://ares-offline.invalid/workbench');await page.waitForTimeout(700);await page.screenshot({path:path.join(out,'webui_task_state.png')});await page.getByText('碰撞模型解释器 · 三视图与透视图',{exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'webui_object_envelope_inspector.png')});
 fs.mkdirSync(path.join(priv,'ui_originals'),{recursive:true});for(const f of fs.readdirSync(out).filter(f=>f.startsWith('webui_')&&f.endsWith('.png')))fs.copyFileSync(path.join(out,f),path.join(priv,'ui_originals',f));
 fs.writeFileSync(path.join(priv,'ui_browser_qa.json'),JSON.stringify({browser:'Chrome headless',viewport:[1920,1080],deviceScaleFactor:1.5,requests,errors:failures,external_requests_allowed:false,backend:'API fixtures; exact source HTML/JS; ReplayCapabilityProvider failure run',camera:{view:'BODY -Y toward +Y',yaw:20*Math.PI/180,pitch:-24*Math.PI/180,source_changes:false}},null,2));await browser.close();if(failures.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
