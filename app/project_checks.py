"""Bounded behavioral checks for model source; never included in generated apps.

These small fixtures catch incorrect helpers before a full browser evaluation.
They are not a browser, and passing them cannot prove import/export behavior.
"""
import json
from . import tools

CHECKS = {'time_format', 'status', 'busy'}
RUNNER = r'''
const vm = require('node:vm');
let input=''; process.stdin.on('data',b=>input+=b);
process.stdin.on('end',()=>{
  try {
    const {source,check}=JSON.parse(input);
    const context=vm.createContext(Object.create(null),{codeGeneration:{strings:false,wasm:false}});
    const fixtures=`
      const app={loaded:false,busy:false};
      const ui={};
      for(const id of ['fileInput','playBtn','seekInput','startInput','endInput','exportBtn','cancelBtn','status']){
        const classes=new Set();
        ui[id]={disabled:false,hidden:false,textContent:'',classList:{
          toggle(name,force){const enabled=force===undefined?!classes.has(name):!!force; if(enabled)classes.add(name);else classes.delete(name);return enabled;},
          add(...names){for(const name of names)classes.add(name);},
          remove(...names){for(const name of names)classes.delete(name);},
          contains(name){return classes.has(name);}
        }};
        globalThis[id]=ui[id];
      }
      const document={getElementById(id){return ui[id]||null;},querySelector(selector){return selector.startsWith('#')?ui[selector.slice(1)]||null:null;}};
      const failures=[];
      function assert(value,message){if(!value)failures.push(message);}
    `;
    const cases={
      time_format:`for(const [value,expected] of [[0,'00:00'],[65,'01:05'],[65.9,'01:05'],[-1,'00:00'],[NaN,'00:00'],[Infinity,'00:00'],[3599,'59:59']]) assert(formatTime(value)===expected,'formatTime('+value+') must return '+expected);for(let i=0;i<41;i++){const value=(i*83+7)/3;const total=Math.floor(value);const expected=String(Math.floor(total/60)).padStart(2,'0')+':'+String(total%60).padStart(2,'0');assert(formatTime(value)===expected,'formatTime('+value+') must return '+expected);}`,
      status:`setStatus('failed',true);assert(ui.status.textContent==='failed'&&ui.status.classList.contains('error'),'Error text/class not set');setStatus('failed again',true);assert(ui.status.classList.contains('error'),'Repeated errors must keep error class');setStatus('ready');assert(ui.status.textContent==='ready'&&!ui.status.classList.contains('error'),'Success must clear previous error class');`,
      busy:`for(const loaded of [false,true])for(const flag of [false,true]){app.loaded=loaded;setBusy(flag);assert(app.loaded===loaded,'setBusy must preserve loaded state');assert(app.busy===flag,'busy state mismatch');assert(ui.fileInput.disabled===flag,'fileInput.disabled expected '+flag+' when busy='+flag+' loaded='+loaded+'; actual='+ui.fileInput.disabled);for(const id of ['playBtn','seekInput','startInput','endInput','exportBtn'])assert(ui[id].disabled===(flag||!loaded),id+'.disabled expected '+(flag||!loaded)+' when busy='+flag+' loaded='+loaded);assert(ui.cancelBtn.hidden===!flag,'Cancel visibility mismatch');}`
    };
    if(!Object.hasOwn(cases,check))throw new Error('Unknown behavioral check');
    vm.runInContext(fixtures+'\n'+source+'\n'+cases[check]+"\nif(failures.length)throw new Error([...new Set(failures)].slice(0,12).join('; '));",context,{timeout:500});
    console.log('behavioral helper check passed');
  }catch(error){console.error(error.message);process.exitCode=1;}
});
'''


async def inspect_helper(source, check):
    if check not in CHECKS:
        raise ValueError('Unknown helper behavioral check')
    payload=json.dumps({'source':source,'check':check}).encode()
    # Fixed runner + untrusted data, through the existing project sandbox.
    # No fixture bytes are added to model output or delivered application files.
    import base64
    encoded=base64.b64encode(RUNNER.encode()).decode()
    loader="eval(Buffer.from('"+encoded+"','base64').toString('utf8'))"
    result=await tools._run_sandboxed(['node','-e',loader],timeout=5,stdin=payload,project=True)
    if result.startswith('[kode keluar 0]'):return []
    # Keep individual failing cases addressable. A repair must not solve one
    # case by breaking a previously passing case; exceptions remain failures.
    detail=result.split('\n',1)[1] if result.startswith('[kode keluar 1]\n') else result
    return ['Helper behavior failed: '+case for case in detail[-1000:].strip().split('; ') if case]
