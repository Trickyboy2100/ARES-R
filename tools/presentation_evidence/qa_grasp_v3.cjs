// Browser-only verification: every request is fulfilled from local evidence files.
const fs=require('fs'),path=require('path');
const {chromium}=require(process.env.ARES_PLAYWRIGHT||'playwright');
let activeBrowser;
(async()=>{
 const out=path.resolve(process.argv[2]);const browser=await chromium.launch({executablePath:process.env.CHROME_BIN||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage']});
 activeBrowser=browser;
 const page=await browser.newPage({viewport:{width:1600,height:1200},serviceWorkers:'block'});const errors=[],requests=[],checks=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{const u=new URL(route.request().url());requests.push(u.href);if(u.hostname!=='grasp-evidence.invalid')return route.abort();const file=path.resolve(out,'.'+decodeURIComponent(u.pathname==='/'?'/index.html':u.pathname));if(!file.startsWith(out+path.sep))return route.abort();const actual=u.pathname==='/'?path.join(out,'index.html'):file;if(!fs.existsSync(actual))return route.fulfill({status:404,body:'missing'});let ext=path.extname(actual),mime={'.html':'text/html','.png':'image/png','.gif':'image/gif','.svg':'image/svg+xml','.json':'application/json','.md':'text/plain'}[ext]||'application/octet-stream';return route.fulfill({status:200,contentType:mime,body:fs.readFileSync(actual)})});
 await page.goto('http://grasp-evidence.invalid/');await page.waitForFunction(()=>window.GRASP_VIEWER_STATUS?.visible>0);
 for(let i=0;i<6;i++){await page.locator('#stages button').nth(i).click();let s=await page.evaluate(()=>window.GRASP_VIEWER_STATUS);if(s.stage!==i||s.visible<=0)throw Error('Stage failed '+i);checks.push({stage:i+1,visible:s.visible})}
 await page.locator('#stages button').nth(3).click();for(const id of ['front','top','iso','full','owned','focus']){await page.locator('#'+id).click();checks.push({control:id,...await page.evaluate(()=>window.GRASP_VIEWER_STATUS)})}
 await page.locator('#boxes').check();await page.locator('#removed').check();await page.locator('#slice').check();checks.push({control:'z_slice',...await page.evaluate(()=>window.GRASP_VIEWER_STATUS)});await page.locator('#reset').click();
 await page.locator('#stages button').nth(3).click();
 await page.screenshot({path:path.join(out,'browser_interactive.png')});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);if(overflow)errors.push('Horizontal page overflow');
 const missing=await page.evaluate(()=>[...document.images].filter(i=>i.complete&&!i.naturalWidth).map(i=>i.src));if(missing.length)errors.push('Broken loaded images: '+missing.join(','));
 const receipt={result:errors.length?'FAIL':'PASS',errors,checks,viewport:[1600,1200],external_requests_allowed:false,all_requests_fulfilled_from_local_files:true,requested_resources:requests.length,source_kind:'BROWSER_QA_NOT_PHYSICAL_DATA'};
 fs.writeFileSync(path.join(out,'browser_qa.json'),JSON.stringify(receipt,null,2)+'\n');await browser.close();if(errors.length)throw Error(errors.join('; '));console.log(JSON.stringify(receipt));
})().catch(async e=>{console.error(e);if(activeBrowser)await activeBrowser.close();process.exitCode=1});
