/* Capture the real app at native 2x resolution. No network/model responses mocked. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.AGENMINI_PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'docs/screenshots');
const session=JSON.parse(fs.readFileSync(path.join(root,'.local-tools/media-session.json'),'utf8'));
assert(session.fixture===true,'A disposable documentation server is required');
const manifest={fixture:true,description:'Real application UI with labelled documentation data, not model output.',screenshots:[]};
(async()=>{
 const browser=await chromium.launch({headless:true});
 const errors=[];
 try{
  const context=await browser.newContext({viewport:{width:1440,height:960},deviceScaleFactor:2,colorScheme:'dark',reducedMotion:'reduce'});
  await context.addInitScript(()=>{try{localStorage.setItem('tema','dark');localStorage.setItem('bot','orchestrator')}catch{}});
  assert((await context.request.post(session.baseURL+'/api/login',{data:{password:session.password},headers:{Origin:session.baseURL}})).ok());
  const page=await context.newPage();page.setDefaultTimeout(12000);page.on('pageerror',e=>errors.push(e.message));
  await page.goto(session.baseURL);await page.waitForFunction(()=>typeof S!=='undefined'&&S.bot?.id==='orchestrator');
  await page.locator('#msgs').waitFor({state:'visible'});
  async function settle(){await page.evaluate(async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.complete?Promise.resolve():new Promise(r=>{i.onload=r;i.onerror=r})));document.activeElement?.blur()});await page.waitForTimeout(350)}
  async function snap(name){await settle();assert(await page.evaluate(()=>document.documentElement.scrollWidth===innerWidth),'Horizontal page overflow: '+name);await page.screenshot({path:path.join(out,name),type:'png',animations:'disabled',caret:'hide'});manifest.screenshots.push({name,width:(await page.viewportSize()).width*2,height:(await page.viewportSize()).height*2,scale:2});console.log('Captured',name)}
  async function goTo(name){if(await page.locator('#wbClose').isVisible())await page.locator('#wbClose').click();await page.evaluate(name=>go(name),name);await page.waitForTimeout(650)}
  async function select(id,label){await page.locator('[data-select-source="'+id+'"]').click();await page.getByRole('option',{name:label,exact:true}).click()}
  async function focus(selector){await page.evaluate(selector=>{const node=document.querySelector(selector);node.scrollIntoView({block:'start'});node.closest('.page').scrollTop-=32},selector)}
  async function panel(){await page.locator('#workbenchOpen').click();await page.waitForFunction(()=>document.querySelector('#wbFiles option[value="image-tools/export.js"]'));await select('wbFiles','image-tools/export.js');await page.waitForFunction(()=>document.querySelector('#wbEditor').value.includes('export async function'))}
  await snap('chat-desktop.png');
  await panel();await snap('workbench-desktop.png');
  await page.locator('#workbench').screenshot({path:path.join(out,'editor-detail.png'),type:'png',animations:'disabled',caret:'hide'});
  const detail=await page.locator('#workbench').boundingBox();manifest.screenshots.push({name:'editor-detail.png',width:Math.round(detail.width*2),height:Math.round(detail.height*2),scale:2});
  await page.evaluate(()=>document.documentElement.dataset.theme='light');await snap('workbench-light.png');
  await page.evaluate(()=>document.documentElement.dataset.theme='dark');
  await goTo('office');await page.waitForSelector('.office-character');await snap('workspace-desktop.png');
  await page.evaluate(()=>document.documentElement.dataset.theme='light');await snap('workspace-light.png');
  await page.evaluate(()=>document.documentElement.dataset.theme='dark');
  await goTo('ai');await page.waitForSelector('#providerPicker .provider-card');
  await focus('#providerPicker');await snap('providers-desktop.png');
  await goTo('settings');await page.evaluate(()=>document.querySelector('#harnessMode').closest('section').scrollIntoView({block:'start'}));await snap('harness-desktop.png');
  await goTo('ai');await page.locator('[data-mode=local]').click();await page.waitForSelector('#localModelCards .model-card');await snap('runtime-desktop.png');
  await goTo('chat');await page.evaluate(()=>toast('Preview notifikasi · perubahan disimpan.'));await snap('toast-desktop.png');
  await page.evaluate(()=>{document.querySelectorAll('.toast').forEach(n=>n.remove());uiConfirm('Contoh dialog dokumentasi. Perubahan belum akan diterapkan.');});await snap('dialog-desktop.png');await page.keyboard.press('Escape');
  for(const theme of ['light','dark']){await goTo('chat');await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);await snap('mascot-'+theme+'.png')}
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>document.documentElement.dataset.theme='dark');
  await goTo('chat');await snap('chat-mobile.png');await panel();await snap('workbench-mobile.png');
  await goTo('office');await snap('workspace-mobile.png');
  await goTo('ai');await page.evaluate(async()=>{aiDraftMode='router';await loadAI()});await page.waitForSelector('#providerPicker .provider-card');await focus('#providerPicker');await snap('providers-mobile.png');
  await goTo('settings');await page.evaluate(()=>document.querySelector('#harnessMode').closest('section').scrollIntoView({block:'start'}));await snap('harness-mobile.png');
  await goTo('ai');await page.locator('[data-mode=local]').click();await page.waitForSelector('#localModelCards .model-card');await snap('runtime-mobile.png');
  await goTo('chat');await page.evaluate(()=>toast('Preview notifikasi · perubahan disimpan.'));await snap('toast-mobile.png');
  assert.deepEqual(errors,[]);manifest.errors=errors;
  fs.writeFileSync(path.join(out,'capture.json'),JSON.stringify(manifest,null,2)+'\n');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
