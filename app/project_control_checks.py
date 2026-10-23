"""Editor event contracts; evaluator fixtures are never shipped as app source."""

CONTROL_CASES = {'video_controls_onVideoSelected': {'setup': '',
                                    'test': 'const first={},second={},calls=[];const '
                                            'ui={fileInput:{files:[first]}};function '
                                            "loadVideo(file){calls.push(file);}onVideoSelected();ui.fileInput.files=[second];onVideoSelected();ui.fileInput.files=[];onVideoSelected();assert(calls.length===2&&calls[0]===first&&calls[1]===second,'Pass "
                                            'each original File, never the event or the files array; ignore empty '
                                            "selection');"},
 'video_controls_onSeekInput': {'setup': '',
                                'test': 'const document={getElementById(id){return ui[id]||null;}};const '
                                        "ui={seekInput:{value:'1.25'}},calls=[];function "
                                        "seekVideo(value){calls.push(value);}onSeekInput();ui.seekInput.value='3.7';onSeekInput();assert(calls.length===2&&calls[0]===1.25&&calls[1]===3.7,'Forward "
                                        "numeric slider value to seekVideo');"},
 'video_controls_cancelExport': {'setup': '',
                                 'test': 'const '
                                         "app={cancelled:false,busy:true,loaded:true};cancelExport();assert(app.cancelled===true&&app.busy===true&&app.loaded===true,'Only "
                                         "set cancelled');"},
 'video_controls_onPreviewPaused': {'setup': '',
                                    'test': "const ui={playBtn:{textContent:'Pause'},preview:{play(){throw "
                                            "Error('Do not play');},pause(){throw Error('Do not "
                                            "pause');}}};onPreviewPaused();assert(ui.playBtn.textContent==='Play','Paused "
                                            "label must be Play');"},
 'video_controls_syncPreviewLabel': {'setup': '',
                                     'test': 'const '
                                             "ui={preview:{paused:true},playBtn:{textContent:''}};syncPreviewLabel();assert(ui.playBtn.textContent==='Play','paused "
                                             'video: label expected Play, actual '
                                             "'+ui.playBtn.textContent);ui.preview.paused=false;syncPreviewLabel();assert(ui.playBtn.textContent==='Pause','playing "
                                             "video: label expected Pause, actual '+ui.playBtn.textContent);"},
 'video_controls_pauseAtTrimEnd': {'setup': '',
                                   'test': 'let pauses=0;const '
                                           'app={busy:false,end:2.5},ui={preview:{paused:false,currentTime:3,pause(){pauses++;this.paused=true;},play(){throw '
                                           "Error('Never play in "
                                           "timeupdate');}}};pauseAtTrimEnd();assert(pauses===1,'pause at trim "
                                           'end expected one pause, actual '
                                           "'+pauses);ui.preview.paused=false;app.busy=true;pauseAtTrimEnd();assert(pauses===1,'recording "
                                           'must continue beyond preview trim '
                                           "check');app.busy=false;ui.preview.currentTime=1;pauseAtTrimEnd();assert(pauses===1,'do "
                                           'not pause before '
                                           "end');ui.preview.currentTime=2.5;ui.preview.paused=true;pauseAtTrimEnd();assert(pauses===1,'do "
                                           "not pause twice');"},
 'video_controls_copyPreviewTime': {'setup': '',
                                    'test': 'const '
                                            "input={value:0},video={currentTime:1.25};copyPreviewTime(input,video);assert(Number(input.value)===1.25&&video.currentTime===1.25,'input.value "
                                            'must receive video.currentTime; video is '
                                            "read-only');video.currentTime=3.7;copyPreviewTime(input,video);assert(Number(input.value)===3.7,'input.value "
                                            "must follow new video time');"},
 'video_controls_onPreviewTime': {'setup': '',
                                  'test': 'let pauses=0,timelines=0;const '
                                          "app={busy:false,end:2.5},ui={seekInput:{value:0},playBtn:{textContent:''},preview:{currentTime:3,paused:false,pause(){pauses++;this.paused=true;}}};function "
                                          "updateTimeline(){timelines++;}onPreviewTime();assert(Number(ui.seekInput.value)===3,'seek "
                                          'value expected 3, actual '
                                          "'+ui.seekInput.value);assert(pauses===1&&ui.playBtn.textContent==='Play'&&timelines===1,'pause, "
                                          'caption and timeline must all '
                                          "update');app.busy=true;ui.preview.paused=false;onPreviewTime();assert(pauses===1&&ui.playBtn.textContent==='Pause'&&timelines===2,'recording "
                                          'must continue during '
                                          "timeupdate');app.busy=false;ui.preview.currentTime=.7;onPreviewTime();assert(Number(ui.seekInput.value)===.7&&pauses===1&&timelines===3,'normal "
                                          "playback must synchronize position without pausing');"},
 'video_controls_cleanupSourceUrl': {'setup': '',
                                     'test': "const state={objectURL:'blob:input'},revoked=[];const "
                                             "URL={revokeObjectURL(url){revoked.push(url);}};cleanupSourceUrl(state);assert(revoked.length===1&&revoked[0]==='blob:input','revoke "
                                             "original URL');state.objectURL='';cleanupSourceUrl(state);delete "
                                             "state.objectURL;cleanupSourceUrl(state);assert(revoked.length===1,'ignore "
                                             "absent URL');"},
 'video_controls_cleanupDownloadUrl': {'setup': '',
                                       'test': "const state={downloadURL:'blob:input'},revoked=[];const "
                                               "URL={revokeObjectURL(url){revoked.push(url);}};cleanupDownloadUrl(state);assert(revoked.length===1&&revoked[0]==='blob:input','revoke "
                                               'original '
                                               "URL');state.downloadURL='';cleanupDownloadUrl(state);delete "
                                               "state.downloadURL;cleanupDownloadUrl(state);assert(revoked.length===1,'ignore "
                                               "absent URL');"},
 'video_controls_cleanupEditor': {'setup': '',
                                  'test': 'const '
                                          "app={objectURL:'blob:input',downloadURL:'blob:output',raf:42},revoked=[],cancelled=[];const "
                                          "URL={revokeObjectURL(value){revoked.push(value);}},window={cancelAnimationFrame(value){cancelled.push(value);}};cleanupEditor(app);assert(revoked.length===2&&revoked.includes('blob:input')&&revoked.includes('blob:output')&&cancelled.length===1&&cancelled[0]===42,'release "
                                          'both URLs and RAF using supplied '
                                          "state');revoked.length=0;cancelled.length=0;app.objectURL='';app.downloadURL='';app.raf=null;cleanupEditor(app);assert(!revoked.length&&!cancelled.length,'ignore "
                                          'absent '
                                          "resources');app.raf=0;cleanupEditor(app);assert(cancelled.length===1&&cancelled[0]===0,'RAF "
                                          "zero is valid');"},
 'video_controls_isEditableTarget': {'setup': '',
                                     'test': 'for(const target of '
                                             "[{tagName:'INPUT'},{tagName:'TEXTAREA'},{tagName:'DIV',isContentEditable:true}])assert(isEditableTarget(target)===true,'text "
                                             "input target must return Boolean true');for(const target of "
                                             "[null,undefined,{tagName:'BUTTON'},{tagName:'DIV',isContentEditable:false}])assert(isEditableTarget(target)===false,'non-editable "
                                             "or missing target must return Boolean false');"},
 'video_controls_timelineFraction': {'setup': '',
                                     'test': "assert(Math.abs(timelineFraction(30,10,100)-.2)<1e-9,'fraction must "
                                             'be click offset divided by '
                                             "width');assert(timelineFraction(-20,10,100)===0,'clamp before lane "
                                             "to zero');assert(timelineFraction(150,10,100)===1,'clamp after lane "
                                             'to '
                                             "one');assert(timelineFraction(30,10,0)===null&&timelineFraction(30,10,-1)===null,'ignore "
                                             "zero/negative lane width');"},
 'video_controls_onEditorKey': {'setup': '',
                                'test': 'let toggles=0,prevented=0;const '
                                        'app={busy:false,cancelled:false};function togglePlay(){toggles++;}const '
                                        "event={key:' "
                                        "',code:'Space',target:{tagName:'DIV'},preventDefault(){prevented++;}};onEditorKey(event);assert(toggles===1&&prevented===1,'Space "
                                        "outside input must prevent default and toggle playback');for(const "
                                        'target of '
                                        "[{tagName:'INPUT'},{tagName:'TEXTAREA'},{tagName:'DIV',isContentEditable:true}]){event.target=target;onEditorKey(event);}assert(toggles===1&&prevented===1,'Space "
                                        'must remain editable inside text '
                                        "targets');event.key='Escape';event.code='Escape';app.busy=true;onEditorKey(event);assert(app.cancelled===true,'Escape "
                                        'during recording must '
                                        "cancel');app.cancelled=false;app.busy=false;onEditorKey(event);assert(app.cancelled===false,'Escape "
                                        'while idle must not '
                                        "cancel');event.key='x';event.code='KeyX';onEditorKey(event);assert(toggles===1,'ignore "
                                        'unrelated '
                                        "keys');app.busy=true;app.cancelled=false;onEditorKey({key:'a',target:{tagName:'DIV'}});assert(app.cancelled===false,'ordinary "
                                        "keys must not cancel export');"},
 'video_controls_onTimelineClick': {'setup': '',
                                    'test': 'const '
                                            'app={loaded:true,busy:false,duration:10},ui={preview:{currentTime:0}};let '
                                            'updates=0;function updateTimeline(){updates++;}const '
                                            'rect={left:10,width:100},lane={getBoundingClientRect(){return '
                                            "rect;}},target={closest(selector){assert(selector==='.track-lane','use "
                                            "track-lane ancestor');return lane;},getBoundingClientRect(){return "
                                            "{left:999,width:1000};}},event={target,clientX:40};onTimelineClick(event);assert(Math.abs(ui.preview.currentTime-3)<1e-9,'seek "
                                            'from lane rectangle expected 3, actual '
                                            "'+ui.preview.currentTime);event.clientX=-20;onTimelineClick(event);assert(ui.preview.currentTime===0,'clamp "
                                            'before '
                                            "lane');event.clientX=150;onTimelineClick(event);assert(ui.preview.currentTime===10,'clamp "
                                            'after '
                                            "lane');app.busy=true;event.clientX=40;onTimelineClick(event);assert(ui.preview.currentTime===10,'ignore "
                                            'timeline while '
                                            "recording');app.busy=false;app.loaded=false;onTimelineClick(event);assert(ui.preview.currentTime===10,'ignore "
                                            "without loaded clip');app.loaded=true;event.target={closest(){return "
                                            "null;}};onTimelineClick(event);assert(ui.preview.currentTime===10,'ignore "
                                            'clicks outside '
                                            "lane');event.target=target;rect.width=0;onTimelineClick(event);assert(ui.preview.currentTime===10,'ignore "
                                            "empty lane width');"},
 'video_controls_bindImportControls': {'setup': '\n'
                                                'const effects=[];\n'
                                                'function control(){const listeners={};return '
                                                "{addEventListener(name,fn){if(typeof fn!=='function')throw "
                                                "Error('Register a callback, do not call it during "
                                                "binding');(listeners[name]??=[]).push(fn);},fire(name,extra={}){const "
                                                'event={type:name,target:this,...extra};for(const fn of '
                                                'listeners[name]||[])fn.call(this,event);if(typeof '
                                                "this['on'+name]==='function')this['on'+name].call(this,event);return "
                                                'event;}};}\n'
                                                'const '
                                                "ui=Object.fromEntries(['fileInput','playBtn','seekInput','startInput','endInput','titleInput','exportBtn','cancelBtn','preview','timeline'].map(id=>[id,control()]));\n"
                                                'const '
                                                "document=control(),window=control();document.getElementById=id=>ui[id]||null;document.querySelector=selector=>selector.startsWith('#')?ui[selector.slice(1)]||null:null;\n"
                                                'const '
                                                "file={name:'real.mp4'};ui.fileInput.files=[file];ui.seekInput.value='1.25';function "
                                                "loadVideo(v){effects.push(['file',v]);}function "
                                                "togglePlay(){effects.push(['play']);}function "
                                                "seekVideo(v){effects.push(['seek',v]);}",
                                       'test': "bindImportControls();assert(effects.length===0,'binding must not "
                                               'execute '
                                               "actions');ui.fileInput.fire('change');ui.playBtn.fire('click');ui.seekInput.fire('input');assert(effects.length===3&&effects[0][0]==='file'&&effects[0][1]===file,'file "
                                               'event must forward original File through '
                                               "handler');assert(effects[1][0]==='play'&&effects[2][0]==='seek'&&effects[2][1]===1.25,'play "
                                               "and numeric seek must work');"},
 'video_controls_bindTrimControls': {'setup': '\n'
                                              'const effects=[];\n'
                                              'function control(){const listeners={};return '
                                              "{addEventListener(name,fn){if(typeof fn!=='function')throw "
                                              "Error('Register a callback, do not call it during "
                                              "binding');(listeners[name]??=[]).push(fn);},fire(name,extra={}){const "
                                              'event={type:name,target:this,...extra};for(const fn of '
                                              'listeners[name]||[])fn.call(this,event);if(typeof '
                                              "this['on'+name]==='function')this['on'+name].call(this,event);return "
                                              'event;}};}\n'
                                              'const '
                                              "ui=Object.fromEntries(['fileInput','playBtn','seekInput','startInput','endInput','titleInput','exportBtn','cancelBtn','preview','timeline'].map(id=>[id,control()]));\n"
                                              'const '
                                              "document=control(),window=control();document.getElementById=id=>ui[id]||null;document.querySelector=selector=>selector.startsWith('#')?ui[selector.slice(1)]||null:null;\n"
                                              "function validateTrim(){effects.push('trim');}function "
                                              "updateText(){effects.push('text');}",
                                     'test': "bindTrimControls();assert(!effects.length,'do not execute while "
                                             "binding');for(const input of [ui.startInput,ui.endInput]){const "
                                             "before=effects.length;input.fire('input');input.fire('change');assert(effects.length>before&&effects.slice(before).every(value=>value==='trim'),'editing "
                                             'either trim bound must reach validateTrim through input or '
                                             "change');}const "
                                             "before=effects.length;ui.titleInput.fire('input');assert(effects.length===before+1&&effects.at(-1)==='text','title "
                                             "input must reach updateText exactly once');"},
 'video_controls_bindExportControls': {'setup': '\n'
                                                'const effects=[];\n'
                                                'function control(){const listeners={};return '
                                                "{addEventListener(name,fn){if(typeof fn!=='function')throw "
                                                "Error('Register a callback, do not call it during "
                                                "binding');(listeners[name]??=[]).push(fn);},fire(name,extra={}){const "
                                                'event={type:name,target:this,...extra};for(const fn of '
                                                'listeners[name]||[])fn.call(this,event);if(typeof '
                                                "this['on'+name]==='function')this['on'+name].call(this,event);return "
                                                'event;}};}\n'
                                                'const '
                                                "ui=Object.fromEntries(['fileInput','playBtn','seekInput','startInput','endInput','titleInput','exportBtn','cancelBtn','preview','timeline'].map(id=>[id,control()]));\n"
                                                'const '
                                                "document=control(),window=control();document.getElementById=id=>ui[id]||null;document.querySelector=selector=>selector.startsWith('#')?ui[selector.slice(1)]||null:null;\n"
                                                'const app={busy:false,cancelled:false};function '
                                                "exportVideo(){effects.push('export');}",
                                       'test': "bindExportControls();assert(!effects.length&&!app.cancelled,'binding "
                                               'must not export or cancel '
                                               'immediately\');ui.exportBtn.fire(\'click\');assert(JSON.stringify(effects)===\'["export"]\',\'export '
                                               'click must call exportVideo '
                                               "once');app.busy=true;ui.cancelBtn.fire('click');assert(app.cancelled===true&&app.busy===true,'cancel "
                                               "click must request cancellation without clearing busy');"},
 'video_controls_bindPreviewControls': {'setup': '\n'
                                                 'const effects=[];\n'
                                                 'function control(){const listeners={};return '
                                                 "{addEventListener(name,fn){if(typeof fn!=='function')throw "
                                                 "Error('Register a callback, do not call it during "
                                                 "binding');(listeners[name]??=[]).push(fn);},fire(name,extra={}){const "
                                                 'event={type:name,target:this,...extra};for(const fn of '
                                                 'listeners[name]||[])fn.call(this,event);if(typeof '
                                                 "this['on'+name]==='function')this['on'+name].call(this,event);return "
                                                 'event;}};}\n'
                                                 'const '
                                                 "ui=Object.fromEntries(['fileInput','playBtn','seekInput','startInput','endInput','titleInput','exportBtn','cancelBtn','preview','timeline'].map(id=>[id,control()]));\n"
                                                 'const '
                                                 "document=control(),window=control();document.getElementById=id=>ui[id]||null;document.querySelector=selector=>selector.startsWith('#')?ui[selector.slice(1)]||null:null;\n"
                                                 'const app={busy:false,end:2.5};let '
                                                 "pauses=0;ui.preview.currentTime=3;ui.preview.paused=false;ui.preview.pause=function(){pauses++;this.paused=true;};ui.seekInput.value=0;ui.playBtn.textContent='Pause';function "
                                                 "updateTimeline(){effects.push('timeline');}",
                                        'test': "bindPreviewControls();assert(!pauses&&!effects.length,'binding "
                                                'must not affect '
                                                "playback');ui.preview.fire('timeupdate');assert(pauses===1&&Number(ui.seekInput.value)===3&&ui.playBtn.textContent==='Play'&&effects.length===1,'timeupdate "
                                                'must synchronize preview and stop at '
                                                "trim');ui.playBtn.textContent='Pause';ui.preview.fire('pause');assert(ui.playBtn.textContent==='Play'&&pauses===1,'pause "
                                                'event must only refresh '
                                                "label');ui.playBtn.textContent='Pause';ui.preview.fire('ended');assert(ui.playBtn.textContent==='Play'&&pauses===1,'ended "
                                                "event must refresh label without pausing twice');"},
 'video_controls_bindEditorControls': {'setup': '\n'
                                                'const effects=[];\n'
                                                'function control(){const listeners={};return '
                                                "{addEventListener(name,fn){if(typeof fn!=='function')throw "
                                                "Error('Register a callback, do not call it during "
                                                "binding');(listeners[name]??=[]).push(fn);},fire(name,extra={}){const "
                                                'event={type:name,target:this,...extra};for(const fn of '
                                                'listeners[name]||[])fn.call(this,event);if(typeof '
                                                "this['on'+name]==='function')this['on'+name].call(this,event);return "
                                                'event;}};}\n'
                                                'const '
                                                "ui=Object.fromEntries(['fileInput','playBtn','seekInput','startInput','endInput','titleInput','exportBtn','cancelBtn','preview','timeline'].map(id=>[id,control()]));\n"
                                                'const '
                                                "document=control(),window=control();document.getElementById=id=>ui[id]||null;document.querySelector=selector=>selector.startsWith('#')?ui[selector.slice(1)]||null:null;\n"
                                                'const '
                                                "app={loaded:true,busy:false,cancelled:false,duration:10,objectURL:'blob:input',downloadURL:'blob:output',raf:42};ui.preview.currentTime=0;const "
                                                'revoked=[],cancelled=[];const '
                                                'URL={revokeObjectURL(v){revoked.push(v);}};window.cancelAnimationFrame=v=>cancelled.push(v);function '
                                                "updateTimeline(){effects.push('timeline');}function "
                                                "togglePlay(){effects.push('toggle');}",
                                       'test': "bindEditorControls();window.fire('load');assert(!effects.length&&!revoked.length&&!cancelled.length,'binding "
                                               "must not run cleanup/actions');const "
                                               'lane={getBoundingClientRect(){return '
                                               '{left:10,width:100};}},target={closest(){return '
                                               "lane;}};ui.timeline.fire('click',{target,clientX:40});assert(Math.abs(ui.preview.currentTime-3)<1e-9,'timeline "
                                               "event must reach lane-based seek');document.fire('keydown',{key:' "
                                               "',code:'Space',target:{tagName:'DIV'},preventDefault(){effects.push('prevent');}});assert(effects.includes('toggle')&&effects.includes('prevent'),'keyboard "
                                               'must reach playback '
                                               "handler');app.busy=true;document.fire('keydown',{key:'Escape',code:'Escape'});assert(app.cancelled===true,'Escape "
                                               'must reach cancellation '
                                               "handler');window.fire('beforeunload');assert(revoked.length===2&&revoked.includes('blob:input')&&revoked.includes('blob:output')&&cancelled.length===1&&cancelled[0]===42,'beforeunload "
                                               "must give cleanupEditor the original app object, not an event');"},
 'video_controls_initEditor': {'setup': 'const effects=[];function '
                                        "bindImportControls(){effects.push('bindImportControls');}function "
                                        "bindTrimControls(){effects.push('bindTrimControls');}function "
                                        "bindExportControls(){effects.push('bindExportControls');}function "
                                        "bindPreviewControls(){effects.push('bindPreviewControls');}function "
                                        "bindEditorControls(){effects.push('bindEditorControls');}function "
                                        "setBusy(value){assert(value===false,'initial busy must be Boolean "
                                        "false');effects.push('busy');}function "
                                        "updateText(){effects.push('text');}function "
                                        "setStatus(message){assert(/import/i.test(message),'honest import "
                                        "status');effects.push('status');}",
                               'test': 'assert(JSON.stringify(effects)===JSON.stringify(["bindImportControls", '
                                       '"bindTrimControls", "bindExportControls", "bindPreviewControls", '
                                       '"bindEditorControls", "busy", "text", "status"]),\'initialize every group '
                                       "and idle state exactly once');"},
 'video_controls_isSpaceEvent': {'setup': '',
                                 'test': "for(const event of [{key:' '},{code:'Space'},{key:' "
                                         "',code:'Space'}])assert(isSpaceEvent(event)===true,'Space "
                                         "key/code');for(const event of "
                                         "[{key:'a'},{key:'Escape'},{}])assert(isSpaceEvent(event)===false,'other "
                                         "keys');"},
 'video_controls_cancelFromKey': {'setup': '',
                                  'test': 'const app={busy:false},calls=[];function '
                                          "cancelExport(){calls.push('cancel');}for(const busy of "
                                          "[false,true])for(const key of ['a',' "
                                          "','Escape']){app.busy=busy;calls.length=0;cancelFromKey({key});assert(calls.length===Number(busy&&key==='Escape'),'only "
                                          "busy Escape cancels');}"},
 'video_controls_playFromKey': {'setup': '',
                                'test': "const effects=[];function togglePlay(){effects.push('play');}for(const "
                                        'target of '
                                        "[{tagName:'INPUT'},{tagName:'TEXTAREA'},{tagName:'DIV',isContentEditable:true},{tagName:'DIV'},null])for(const "
                                        "key of ['a',' "
                                        "','Escape']){effects.length=0;playFromKey({key,target,preventDefault(){effects.push('prevent');}});const "
                                        "should=key===' "
                                        "'&&!(target&&(target.tagName==='INPUT'||target.tagName==='TEXTAREA'||target.isContentEditable));assert(JSON.stringify(effects)===JSON.stringify(should?['prevent','play']:[]),'respect "
                                        "key and editable target');}"},
 'video_controls_cleanupOnExit': {'setup': '',
                                  'test': 'const '
                                          "app={objectURL:'blob:input',downloadURL:'blob:output',raf:42},revoked=[],cancelled=[];const "
                                          "URL={revokeObjectURL(url){revoked.push(url);}},window={cancelAnimationFrame(id){cancelled.push(id);}};cleanupOnExit({type:'beforeunload'});assert(revoked.length===2&&revoked.includes(app.objectURL)&&revoked.includes(app.downloadURL)&&cancelled.length===1&&cancelled[0]===42,'release "
                                          "resources from original global app, never the browser event');"}}
