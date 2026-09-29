import {
  initCatalystVRM,
  mountAvatar,
  setCatalystAvatarState,
  setCatalystSpeechLevel,
  setCatalystAppearance,
  setCatalystExpression,
  setCatalystGesture,
  setCatalystMotionMode,
  isCatalystVRMLive,
} from '/catalyst-vrm.js';

const $ = (id) => document.getElementById(id);
const state = {
  session: null,
  admin: false,
  attachments: [],
  audio: null,
  audioContext: null,
  analyser: null,
  streaming: false,
  live: false,
  recognition: null,
  recognitionSupported: false,
  recognitionRestart: null,
  recognitionBusy: false,
  currentPage: 'chat',
  appearance: 'signature',
  expression: 'neutral',
  motion: 'full',
  gesture: 'none',
  prefs: {},
  runtimeLive: false,
};

const looks = [
  { id:'signature', image:'/assets/catalyst/avatar_01.png', name:'Signature', desc:'Catalyst\'s default signature look.' },
  { id:'lounge', image:'/assets/catalyst/avatar_05.png', name:'Lounge', desc:'Soft, relaxed everyday presentation.' },
  { id:'focus', image:'/assets/catalyst/avatar_07.png', name:'Focus', desc:'Deep-work creator presentation.' },
  { id:'night', image:'/assets/catalyst/avatar_04.png', name:'Night', desc:'Dark evening presentation.' },
];
const expressions = [
  ['neutral','Neutral'], ['happy','Warm'], ['curious','Curious'], ['thinking','Thinking'],
  ['serious','Focused'], ['surprised','Surprised'], ['concerned','Concerned'], ['playful','Playful'], ['sad','Soft'],
];

const api = async (path, options = {}) => {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData) && options.body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, { credentials:'same-origin', ...options, headers });
  const text = await response.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { raw:text }; }
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
};

const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const storage = {
  get(key, fallback = null) { try { return window.localStorage?.getItem(key) ?? fallback; } catch (_) { return fallback; } },
  set(key, value) { try { window.localStorage?.setItem(key, String(value)); return true; } catch (_) { return false; } },
  remove(key) { try { window.localStorage?.removeItem(key); } catch (_) {} },
};
const toast = (message) => {
  const el = $('toast'); if (!el) return;
  el.textContent = message; el.classList.add('show');
  clearTimeout(window.__catalystToast);
  window.__catalystToast = setTimeout(() => el.classList.remove('show'), 2800);
};
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function openModal(id){$(id)?.classList.add('show');}
function closeModal(id){$(id)?.classList.remove('show');}
document.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => closeModal(b.dataset.close)));
document.querySelectorAll('.modal').forEach((m) => m.addEventListener('click', (e) => { if (e.target === m) m.classList.remove('show'); }));

async function savePrefs(changes = {}) {
  state.prefs = { ...state.prefs, ...changes };
  try { state.prefs = await api('/api/preferences', { method:'PATCH', body:JSON.stringify(changes) }); } catch (_) { /* local fallback keeps the experience working */ }
  Object.entries(changes).forEach(([k,v]) => storage.set(`catalyst.pref.${k}`, typeof v === 'boolean' ? (v ? '1':'0') : v));
  return state.prefs;
}

async function loadPrefs() {
  try { state.prefs = await api('/api/preferences'); }
  catch (_) {
    state.prefs = {
      theme: storage.get('catalyst.pref.theme','dark'), motion: storage.get('catalyst.pref.motion','full'),
      voice_auto: storage.get('catalyst.pref.voice_auto') === '1' || storage.get('catalyst.voiceAuto') === '1',
      live_auto: storage.get('catalyst.pref.live_auto') === '1' || storage.get('catalyst.liveAuto') === '1',
      compact_mode: storage.get('catalyst.pref.compact_mode') === '1', show_activity: storage.get('catalyst.pref.show_activity','1') !== '0',
      use_memory: storage.get('catalyst.pref.use_memory','1') !== '0', confirm_actions: storage.get('catalyst.pref.confirm_actions','1') !== '0',
      appearance: state.appearance,
    };
  }
  document.documentElement.dataset.theme = state.prefs.theme || 'dark';
  document.documentElement.dataset.motion = state.prefs.motion || 'full';
  document.documentElement.classList.toggle('compact', !!state.prefs.compact_mode);
  state.motion = state.prefs.motion || 'full';
  setCatalystMotionMode(state.motion);
}

function page(name) {
  state.currentPage = name;
  document.querySelectorAll('.page').forEach((x) => x.classList.toggle('active', x.id === `page-${name}`));
  document.querySelectorAll('.nav-item[data-page]').forEach((x) => x.classList.toggle('active', x.dataset.page === name));
  $('sidebar')?.classList.remove('open');
  if (name === 'live') {
    mountAvatar('liveAvatarWrap');
    if (state.prefs.live_auto && !state.live) startLiveTalk();
  } else if (name === 'chat') mountAvatar('avatarWrap');
  if (name === 'memory') loadMemory();
  if (name === 'missions') loadMissions();
  if (name === 'library') loadLibrary();
  if (name === 'projects') loadProjects();
}
document.querySelectorAll('.nav-item[data-page]').forEach((b) => b.addEventListener('click', () => page(b.dataset.page)));
$('menuBtn')?.addEventListener('click', () => $('sidebar')?.classList.toggle('open'));
$('settingsBtn')?.addEventListener('click', () => { openModal('settingsModal'); loadSettings(); });
$('topSettings')?.addEventListener('click', () => $('settingsBtn')?.click());
$('creatorBtn')?.addEventListener('click', () => openModal('creatorModal'));
$('lookBtn')?.addEventListener('click', () => { renderLooks(); openModal('appearanceModal'); });
$('lookFromAvatar')?.addEventListener('click', () => $('lookBtn')?.click());
$('studioBtn')?.addEventListener('click', () => openStudio());
$('topOptions')?.addEventListener('click', () => { openModal('optionsModal'); refreshOptions(); });
$('composerOptions')?.addEventListener('click', () => { openModal('optionsModal'); refreshOptions(); });
$('optionsAppearance')?.addEventListener('click', () => { closeModal('optionsModal'); $('lookBtn')?.click(); });
$('optionsStudio')?.addEventListener('click', () => { closeModal('optionsModal'); openStudio(); });
$('optionsRefresh')?.addEventListener('click', refreshOptions);

function setState(next, hint = '', emotion = 'neutral', sync = true, extras = {}) {
  const map = {
    idle:['Idle','Ready when you are.'], listening:['Listening','I’m listening.'], thinking:['Thinking','Working through it.'],
    speaking:['Speaking','Talking with you.'], interrupted:['Listening','I stopped to listen.'], success:['Done','Finished.'],
    error:['Attention','Something needs attention.'], away:['Away','Quiet for now.'],
  };
  const m = map[next] || map.idle;
  $('avatarState').textContent = m[0].toUpperCase(); $('captionState').textContent = m[0]; $('captionHint').textContent = hint || m[1];
  $('topState').textContent = next === 'speaking' ? 'Catalyst is speaking' : next === 'thinking' ? 'Catalyst is thinking' : next === 'listening' ? 'Catalyst is listening' : 'Catalyst is here';
  $('sideStatus').textContent = hint || m[1]; $('avatarWrap').dataset.state = next;
  setCatalystAvatarState({ state:next, emotion, hint, gesture:extras.gesture || state.gesture, motion:state.motion, speech_level:extras.speech_level || 0 });
  if (state.currentPage === 'live') $('liveState').textContent = m[0];
  if (sync) fetch(`/api/avatar/state?state=${encodeURIComponent(next)}&emotion=${encodeURIComponent(emotion)}&hint=${encodeURIComponent(hint || m[1])}&action=${encodeURIComponent(extras.action || '')}&source=ui`, { method:'POST', credentials:'same-origin' }).catch(() => {});
}

function welcomeHTML(){return `<div class="welcome"><div class="welcome-orb">✦</div><h2>Hey. I'm Catalyst.</h2><p>Your conversation, projects, memory and tools stay connected here.</p><div class="suggestions"><button data-prompt="What should we work on today?">What should we work on today?</button><button data-prompt="Show me the current Catalyst status.">Current Catalyst status</button><button data-prompt="Plan my next project with me.">Plan a project</button></div></div>`;}
function wireSuggestions(){document.querySelectorAll('[data-prompt]').forEach((b)=>{b.onclick=()=>{$('prompt').value=b.dataset.prompt;send();};});}
function addWelcome(){if($('messages')){$('messages').innerHTML=welcomeHTML();wireSuggestions();}}

function addMessage(text, role='assistant', meta='') {
  const d=document.createElement('div'); d.className=`message ${role}`;
  d.innerHTML=`<div class="message-role">${role==='user'?'You':'Catalyst'}</div><div class="bubble">${esc(text).replace(/\n/g,'<br>')}</div>${meta?`<div class="message-meta">${esc(meta)}</div>`:''}`;
  $('messages').appendChild(d); $('messages').scrollTop=$('messages').scrollHeight; return d;
}
function addActivity(text){
  if (!state.prefs.show_activity) return null;
  const d=document.createElement('div'); d.className='message activity';
  d.innerHTML=`<div class="message-role">Activity</div><div class="bubble">${esc(text)}</div>`;
  $('messages').appendChild(d); $('messages').scrollTop=$('messages').scrollHeight; return d;
}

async function ensureSession() {
  if (state.session && state.prefs.keep_session !== false) return state.session;
  const saved=storage.get('catalyst.session');
  if (saved && state.prefs.keep_session !== false) {
    try { await api(`/api/sessions/${encodeURIComponent(saved)}`); state.session=saved; return state.session; } catch (_) { storage.remove('catalyst.session'); }
  }
  const r=await api('/api/sessions',{method:'POST'}); state.session=r.session_id; storage.set('catalyst.session',state.session); await loadRecentChats(); return state.session;
}

function processSSEText(raw, pending, activityEl) {
  const line=raw.split('\n').find((x)=>x.startsWith('data:')); if(!line) return {answer:null,done:false};
  const payload=line.slice(5).trim(); if(!payload) return {answer:null,done:false};
  let event; try{event=JSON.parse(payload);}catch(_){return {answer:null,done:false};}
  if(event.type==='step'){ if(activityEl) activityEl.querySelector('.bubble').textContent=`Working · step ${event.step}${event.strategy?` · ${event.strategy}`:''}`; setState('thinking','Working through the next step.','focused'); }
  if(event.type==='tool_calls'){ if(activityEl) activityEl.querySelector('.bubble').textContent=`Using ${event.count || 1} tool${event.count===1?'':'s'} safely.`; setState('thinking','Using a Catalyst tool.','focused',true,{action:'think'}); }
  if(event.type==='tool_result'){ if(activityEl) activityEl.querySelector('.bubble').textContent=`Tool complete · ${event.tool || 'operation'}`; }
  if(['content','delta','token','text'].includes(event.type)){ const t=event.text||event.delta||event.content||''; const existing=pending.dataset.answer||''; const answer=existing+t; pending.dataset.answer=answer; pending.querySelector('.bubble').innerHTML=esc(answer).replace(/\n/g,'<br>'); $('messages').scrollTop=$('messages').scrollHeight; setState('speaking','Catalyst is composing the response.','warm'); return {answer,done:false}; }
  if(['done','answer','final'].includes(event.type)){ const answer=event.answer||event.text||pending.dataset.answer||''; pending.dataset.answer=answer; pending.querySelector('.bubble').innerHTML=esc(answer).replace(/\n/g,'<br>'); return {answer,done:true,event}; }
  if(event.type==='error') throw new Error(event.error || 'Catalyst encountered an error.');
  return {answer:pending.dataset.answer||'',done:false};
}

async function send(overrideText=null,{fromLive=false}={}) {
  const input=$('prompt'); const text=String(overrideText ?? input.value).trim(); if(!text || state.streaming) return '';
  if(overrideText===null){input.value='';input.style.height='auto';}
  addMessage(text,'user'); await ensureSession(); state.streaming=true;
  setState('thinking',fromLive?'Thinking about what you said.':'Thinking through your request.','focused',true,{action:'think'});
  const activityEl=addActivity('Preparing context and tools…');
  const pending=addMessage('','assistant'); pending.dataset.answer='';
  try{
    const response=await fetch('/api/chat/stream',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','Accept':'text/event-stream'},body:JSON.stringify({message:text,session_id:state.session,attachments:state.attachments})});
    if(!response.ok){let detail=`HTTP ${response.status}`;try{const err=await response.json();detail=err.detail||detail;}catch(_){}throw new Error(detail);}
    if(!response.body) throw new Error('Catalyst streaming response is unavailable.');
    const reader=response.body.getReader(); const decoder=new TextDecoder(); let buffer=''; let done=false; let finalAnswer='';
    while(!done){
      const {value,done:readerDone}=await reader.read(); buffer += decoder.decode(value||new Uint8Array(),{stream:!readerDone});
      const events=buffer.split('\n\n'); buffer=events.pop()||'';
      for(const raw of events){const result=processSSEText(raw,pending,activityEl);if(result.answer!==null)finalAnswer=result.answer;if(result.done){done=true;break;}}
      if(readerDone){if(buffer.trim()){const result=processSSEText(buffer,pending,activityEl);if(result.answer!==null)finalAnswer=result.answer;if(result.done)done=true;}break;}
    }
    if(!finalAnswer) finalAnswer=pending.dataset.answer||'I did not receive a response.';
    pending.dataset.answer=finalAnswer; pending.querySelector('.bubble').innerHTML=esc(finalAnswer).replace(/\n/g,'<br>');
    activityEl?.remove(); setState('success','Response complete.','warm');
    if(fromLive || state.prefs.voice_auto) await speak(finalAnswer,{liveResume:fromLive});
    setTimeout(()=>setState(state.live?'listening':'idle',state.live?'Listening for you.':'Ready when you are.'),750);
    await loadRecentChats(); return finalAnswer;
  }catch(e){
    activityEl?.remove(); pending.querySelector('.bubble').textContent=e.message; setState('error',e.message,'concerned'); toast(e.message); setTimeout(()=>setState(state.live?'listening':'idle'),1100); return '';
  }finally{state.streaming=false;}
}

$('sendBtn')?.addEventListener('click',()=>send());
$('prompt')?.addEventListener('keydown',(e)=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}});
$('prompt')?.addEventListener('input',(e)=>{e.target.style.height='auto';e.target.style.height=Math.min(150,e.target.scrollHeight)+'px';});
$('newChat')?.addEventListener('click',async()=>{try{const r=await api('/api/sessions',{method:'POST'});state.session=r.session_id;storage.set('catalyst.session',state.session);state.attachments=[];$('attachmentRow').innerHTML='';addWelcome();await loadRecentChats();toast('New conversation ready.');}catch(e){toast(e.message);}});
$('clearChat')?.addEventListener('click',()=>{if($('messages')){addWelcome();toast('Conversation view cleared.');}});

async function speak(text,{liveResume=false}={}){
  if(!text?.trim()) return;
  if(state.audio){try{state.audio.pause();state.audio.currentTime=0;}catch(_){}state.audio=null;setCatalystSpeechLevel(0);}
  if(state.recognition&&state.live)try{state.recognition.stop();}catch(_){ }
  try{
    setState('speaking','Generating voice output…','warm',true,{action:'speak'});
    const r=await api(`/api/voice/speak?text=${encodeURIComponent(text)}`,{method:'POST'}); const name=r.artifact?.name; if(!name)throw new Error('No audio artifact returned.');
    const audio=new Audio(`/api/artifacts/${encodeURIComponent(name)}`); audio.preload='auto'; state.audio=audio;
    audio.onplay=()=>setState('speaking','Talking with you.','warm',true,{action:'speak'});
    audio.onended=()=>{state.audio=null;setCatalystSpeechLevel(0);setState(state.live?'listening':'idle',state.live?'Listening for you.':'Ready when you are.');if(liveResume)scheduleRecognitionRestart();};
    audio.onerror=()=>{state.audio=null;setCatalystSpeechLevel(0);setState('error','Voice playback failed.','concerned');if(liveResume)scheduleRecognitionRestart();};
    await audio.play();
    try{
      state.audioContext ||= new(window.AudioContext||window.webkitAudioContext)();
      const source=state.audioContext.createMediaElementSource(audio); const analyser=state.audioContext.createAnalyser(); analyser.fftSize=512; source.connect(analyser);analyser.connect(state.audioContext.destination);state.analyser=analyser;
      const buffer=new Uint8Array(analyser.fftSize);
      const tick=()=>{if(state.audio!==audio||audio.paused||audio.ended){setCatalystSpeechLevel(0);return;}analyser.getByteTimeDomainData(buffer);let sum=0;for(const n of buffer){const x=(n-128)/128;sum+=x*x;}setCatalystSpeechLevel(Math.min(1,Math.sqrt(sum/buffer.length)*2.7));requestAnimationFrame(tick);};tick();
    }catch(_){ }
  }catch(e){toast(e.message);if(liveResume)scheduleRecognitionRestart();}
}
$('voiceBtn')?.addEventListener('click',()=>{const last=[...document.querySelectorAll('.message.assistant .bubble')].pop()?.textContent;if(last)speak(last);else toast('Nothing to speak yet.');});
$('stopVoiceBtn')?.addEventListener('click',stopVoice);
function stopVoice(){if(state.audio){try{state.audio.pause();state.audio.currentTime=0;}catch(_){}state.audio=null;}setCatalystSpeechLevel(0);if(state.live){setState('listening','Listening for you.');scheduleRecognitionRestart();}else setState('idle','Ready when you are.');}

$('attachBtn')?.addEventListener('click',()=>$('fileInput')?.click());
$('fileInput')?.addEventListener('change',async(e)=>{for(const f of e.target.files||[]){const fd=new FormData();fd.append('file',f);try{const d=await api('/api/attachments',{method:'POST',body:fd});state.attachments.push(d.id);const chip=document.createElement('button');chip.type='button';chip.className='attachment-chip';chip.textContent=`${f.name} ×`;chip.title='Remove attachment';chip.addEventListener('click',()=>{state.attachments=state.attachments.filter(x=>x!==d.id);chip.remove();});$('attachmentRow').appendChild(chip);}catch(err){toast(err.message);}}e.target.value='';});

function renderLooks(targetId='lookGrid'){
  const g=$(targetId);if(!g)return;g.innerHTML=looks.map((l)=>`<button class="look-card ${l.id===state.appearance?'selected':''}" data-look="${l.id}"><img src="${l.image}" alt="${esc(l.name)}"><span>${esc(l.name)}</span><small>${esc(l.desc)}</small><small class="live3d-badge">3D WARDROBE</small></button>`).join('');
  g.querySelectorAll('[data-look]').forEach((b)=>b.addEventListener('click',()=>applyAppearance(b.dataset.look,targetId)));
}
async function applyAppearance(id,source='lookGrid'){
  const target=looks.find(x=>x.id===id);if(!target)return;state.appearance=id;
  const live3d=setCatalystAppearance(id);setCatalystAvatarState({appearance:id});
  if(!live3d){$('catalystAvatar').src=target.image;$('liveFallbackAvatar').src=target.image;}
  try{await api(`/api/avatar/appearance?appearance=${encodeURIComponent(id)}`,{method:'POST'});}catch(_){ }
  await savePrefs({appearance:id}); renderLooks('lookGrid'); renderLooks('studioLookGrid');
  if(source==='lookGrid')closeModal('appearanceModal');toast(`Appearance: ${target.name}`);
}

function renderExpressions(){
  const g=$('expressionGrid');if(!g)return;
  g.innerHTML=expressions.map(([id,label])=>`<button class="expression-choice ${id===state.expression?'selected':''}" data-expression="${id}">${esc(label)}</button>`).join('');
  g.querySelectorAll('[data-expression]').forEach((b)=>b.addEventListener('click',()=>{state.expression=b.dataset.expression;setCatalystExpression(state.expression);setCatalystAvatarState({state:'idle',emotion:state.expression});api(`/api/avatar/state?state=idle&emotion=${encodeURIComponent(state.expression)}&source=studio`,{method:'POST'}).catch(()=>{});renderExpressions();toast(`Expression: ${b.textContent}`);}));
}
function openStudio(){renderLooks('studioLookGrid');renderExpressions();document.querySelectorAll('.studio-choice[data-motion]').forEach((b)=>b.classList.toggle('selected',b.dataset.motion===state.motion));document.querySelectorAll('[data-gesture]').forEach((b)=>b.classList.toggle('selected',b.dataset.gesture===state.gesture));$('studioRuntime').textContent=isCatalystVRMLive()?'3D body status: LIVE VRM 1.0':'3D body status: reference fallback';openModal('studioModal');}
$('studioReset')?.addEventListener('click',()=>{state.expression='neutral';state.gesture='none';state.motion='full';setCatalystExpression('neutral');setCatalystGesture('none');setCatalystMotionMode('full');savePrefs({avatar_expression:'neutral',motion:'full'});openStudio();toast('Catalyst presence reset.');});
document.querySelectorAll('.studio-choice[data-motion]').forEach((b)=>b.addEventListener('click',()=>{state.motion=b.dataset.motion;setCatalystMotionMode(state.motion);savePrefs({motion:state.motion});document.documentElement.dataset.motion=state.motion;document.querySelectorAll('.studio-choice[data-motion]').forEach(x=>x.classList.toggle('selected',x.dataset.motion===state.motion));}));
document.querySelectorAll('[data-gesture]').forEach((b)=>b.addEventListener('click',()=>{state.gesture=b.dataset.gesture;setCatalystGesture(state.gesture);savePrefs({avatar_stage:state.gesture});document.querySelectorAll('[data-gesture]').forEach(x=>x.classList.toggle('selected',x.dataset.gesture===state.gesture));toast(`Gesture: ${b.textContent}`);}));

async function loadSettings(){
  try{
    const [models,providers,dash,avatarState,prefs]=await Promise.all([api('/api/models/catalog'),api('/api/providers'),api('/api/dashboard'),api('/api/avatar/state'),api('/api/preferences')]);
    state.prefs={...state.prefs,...prefs}; state.appearance=avatarState.appearance||state.appearance; state.motion=avatarState.motion||state.prefs.motion||'full';
    $('brainLabel').textContent=`Brain: ${dash.brain?.model||'not configured'}`;
    $('modelOptions').innerHTML=[...(models.primary||[]),...(models.alternatives||[])].map((m)=>{const active=providers.some((p)=>p.active&&p.model===m.model);const preferred=storage.get('catalyst.preferredModel')===m.model;return `<button type="button" class="model-option ${active?'selected':''}" data-model="${esc(m.model)}"><strong>${esc(m.name)} ${active?'<span class="status">ACTIVE</span>':''}</strong><small>${esc(m.description)}${preferred?' · preferred':''}</small></button>`;}).join('');
    $('modelOptions').querySelectorAll('[data-model]').forEach((b)=>b.addEventListener('click',()=>{storage.set('catalyst.preferredModel',b.dataset.model);toast('Preferred model saved for your Catalyst profile.');loadSettings();}));
    $('providerSelect').innerHTML=(providers||[]).map((p)=>`<option value="${esc(p.name)}" ${p.active?'selected':''}>${esc(p.name)}${p.configured?'':' · not configured'}</option>`).join('')||'<option>No providers configured</option>';
    $('providerSelect').onchange=async(e)=>{if(!state.admin){toast('Creator Admin is required to activate a provider.');return;}try{await api(`/api/providers/${encodeURIComponent(e.target.value)}/activate`,{method:'POST'});toast(`Provider activated: ${e.target.value}`);loadSettings();}catch(err){toast(err.message);}};
    $('providerNote').textContent=state.admin?'Provider activation is available.':'Provider activation requires Creator Admin.';
    $('voiceAuto').checked=!!state.prefs.voice_auto; $('chatSpeakToggle').checked=!!state.prefs.voice_auto; $('liveAuto').checked=!!state.prefs.live_auto;
    $('compactMode').checked=!!state.prefs.compact_mode; $('reducedPresence').checked=state.motion==='reduced'; $('themeSelect').value=state.prefs.theme||'dark'; $('motionSelect').value=state.motion;
    if($('useMemoryToggle'))$('useMemoryToggle').checked=state.prefs.use_memory!==false;
    if($('showActivityToggle'))$('showActivityToggle').checked=state.prefs.show_activity!==false;
    if($('confirmActionsToggle'))$('confirmActionsToggle').checked=state.prefs.confirm_actions!==false;
    state.prefs.keep_session=state.prefs.keep_session!==false;
  }catch(e){$('brainLabel').textContent='Brain: unavailable';toast(e.message);}
}
async function setPref(name,value){await savePrefs({[name]:value});}
function setVoiceAuto(on){setPref('voice_auto',!!on);$('voiceAuto').checked=on;$('chatSpeakToggle').checked=on;}
$('voiceAuto')?.addEventListener('change',(e)=>setVoiceAuto(e.target.checked));$('chatSpeakToggle')?.addEventListener('change',(e)=>setVoiceAuto(e.target.checked));
$('liveAuto')?.addEventListener('change',(e)=>setPref('live_auto',e.target.checked));
$('motionSelect')?.addEventListener('change',(e)=>{state.motion=e.target.value;setCatalystMotionMode(state.motion);setPref('motion',state.motion);});
$('reducedPresence')?.addEventListener('change',(e)=>{state.motion=e.target.checked?'reduced':'full';setCatalystMotionMode(state.motion);setPref('motion',state.motion);$('motionSelect').value=state.motion;});
$('compactMode')?.addEventListener('change',(e)=>{document.documentElement.classList.toggle('compact',e.target.checked);setPref('compact_mode',e.target.checked);});
$('themeSelect')?.addEventListener('change',(e)=>{document.documentElement.dataset.theme=e.target.value;setPref('theme',e.target.value);});
$('persistSessionToggle')?.addEventListener('change',(e)=>{state.prefs.keep_session=e.target.checked;setPref('keep_session',e.target.checked);if(!e.target.checked)storage.remove('catalyst.session');});
$('useMemoryToggle')?.addEventListener('change',(e)=>setPref('use_memory',e.target.checked));
$('showActivityToggle')?.addEventListener('change',(e)=>{state.prefs.show_activity=e.target.checked;setPref('show_activity',e.target.checked);$('activityChip')?.classList.toggle('active',e.target.checked);});
$('confirmActionsToggle')?.addEventListener('change',(e)=>setPref('confirm_actions',e.target.checked));
$('refreshSystem')?.addEventListener('click',loadSettings);

async function loadRecentChats(){try{const rows=await api('/api/sessions?limit=12');const list=Array.isArray(rows)?rows:rows.items||rows.sessions||[];$('recentChats').innerHTML=list.length?list.slice(0,8).map((x)=>`<button type="button" class="recent-item ${x.id===state.session?'active':''}" data-session="${esc(x.id)}">${esc(x.title||'Conversation')}</button>`).join(''):'<div class="recent-empty">No conversations yet.</div>';$('recentChats').querySelectorAll('[data-session]').forEach((b)=>b.addEventListener('click',()=>openSession(b.dataset.session)));}catch(_) {}}
async function openSession(id){try{const r=await api(`/api/sessions/${encodeURIComponent(id)}`);state.session=id;storage.set('catalyst.session',id);addConversationRows(r.messages||[]);page('chat');loadRecentChats();}catch(e){toast(e.message);}}
function addConversationRows(rows){$('messages').innerHTML='';if(!rows.length){addWelcome();return;}rows.forEach((row)=>{const role=row.role||row.kind||'assistant';const text=row.content||row.message||row.text||'';if(text)addMessage(text,role==='user'?'user':'assistant');});}
async function loadMemory(){try{const r=await api('/api/memory/stats');$('memoryStats').innerHTML=Object.entries(r).map(([k,v])=>`<div class="stat"><span>${esc(k)}</span><strong>${esc(typeof v==='object'?JSON.stringify(v):v)}</strong></div>`).join('');}catch{$('memoryStats').innerHTML='<div class="empty-card">Memory status unavailable.</div>';}}
async function loadMissions(){try{const r=await api('/api/missions');$('missionCards').innerHTML=(r||[]).slice(0,20).map((x)=>`<div class="data-card"><b>${esc(x.title||x.objective||x.id)}</b><small>${esc(x.status||'queued')}</small></div>`).join('')||'<div class="empty-card">No missions yet.</div>';}catch{$('missionCards').innerHTML='<div class="empty-card">Missions unavailable.</div>';}}
async function loadLibrary(){try{const [a,b]=await Promise.all([api('/api/artifacts'),api('/api/dashboard')]);$('libraryCards').innerHTML=`<div class="data-card"><b>Attachments</b><small>${b.counts?.attachments||0} stored</small></div><div class="data-card"><b>Artifacts</b><small>${a.items?.length||0} available</small></div>`;}catch{$('libraryCards').innerHTML='<div class="empty-card">Library unavailable.</div>';}}
async function loadProjects(){try{const r=await api('/api/project/summary');$('projectCards').innerHTML=`<div class="data-card"><b>Workspace</b><small>${esc(r.root||'Workspace')} · ${r.files||0} files · ${r.indexed_chunks||0} indexed chunks</small></div><div class="data-card"><b>Continuity</b><small>Memory, missions and tools stay connected to this workspace.</small></div>`;}catch{$('projectCards').innerHTML='<div class="empty-card">Workspace status unavailable.</div>';}}

function detectSpeechRecognition(){
  const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;state.recognitionSupported=!!Recognition;if(!Recognition)return;
  const recognition=new Recognition();recognition.continuous=true;recognition.interimResults=true;recognition.lang=navigator.language||'en-US';recognition.maxAlternatives=1;
  recognition.onstart=()=>{if(state.live){state.recognitionBusy=true;$('liveBadge').textContent='LIVE';$('liveState').textContent='Listening…';$('voiceStatus').textContent='Microphone is listening';$('voiceProvider').textContent='Browser speech recognition';$('micBtn').classList.add('active');setState('listening','I’m listening.');}};
  recognition.onresult=(event)=>{let interim='';for(let i=event.resultIndex;i<event.results.length;i++){const txt=event.results[i][0]?.transcript||'';if(event.results[i].isFinal){$('liveTranscript').textContent=txt;send(txt,{fromLive:true});}else interim+=txt;}if(interim)$('liveTranscript').textContent=interim;};
  recognition.onerror=(event)=>{if(state.live&&event.error!=='aborted'){$('voiceStatus').textContent=`Voice input: ${event.error}`;}};
  recognition.onend=()=>{state.recognitionBusy=false;if(state.live&&!state.audio&&!state.streaming)scheduleRecognitionRestart();};state.recognition=recognition;
}
function scheduleRecognitionRestart(){clearTimeout(state.recognitionRestart);if(!state.live||!state.recognitionSupported)return;state.recognitionRestart=setTimeout(()=>{if(!state.live||state.recognitionBusy)return;try{state.recognition.start();}catch(_){ }},450);}
function startLiveTalk(){if(!state.recognitionSupported){toast('This browser does not expose continuous speech recognition. Use a Chromium-based browser for Live Talk.');return;}state.live=true;$('liveBadge').textContent='LIVE';$('liveMainBtn').textContent='Stop Live Talk';$('voiceStatus').textContent='Microphone is starting…';$('liveState').textContent='Listening…';setState('listening','Live Talk is listening.');try{state.recognition.start();}catch(_){scheduleRecognitionRestart();}}
function stopLiveTalk(){state.live=false;clearTimeout(state.recognitionRestart);try{state.recognition?.stop();}catch(_){}if(state.audio)stopVoice();$('liveBadge').textContent='OFFLINE';$('liveMainBtn').textContent='Start Live Talk';$('voiceStatus').textContent='Voice input is off';$('liveState').textContent='Ready';$('micBtn').classList.remove('active');setState('idle','Ready when you are.');}
$('liveMainBtn')?.addEventListener('click',()=>state.live?stopLiveTalk():startLiveTalk());$('liveOptionsBtn')?.addEventListener('click',()=>{openModal('optionsModal');refreshOptions();});$('micBtn')?.addEventListener('click',()=>{page('live');if(!state.live)startLiveTalk();});$('liveFromAvatar')?.addEventListener('click',()=>{page('live');if(!state.live)startLiveTalk();});

async function refreshOptions(){try{const [d,a,p]=await Promise.all([api('/api/dashboard'),api('/api/avatar/state'),api('/api/preferences')]);$('optionsSystemState').textContent=`${d.brain?.model||'No brain configured'} · ${a.state} · ${a.appearance} · ${p.motion||'full'} motion`;}catch{$('optionsSystemState').textContent='System state unavailable.';}}
async function whoami(){try{const r=await api('/api/auth/whoami');state.admin=!!r.admin;$('creatorBtn').innerHTML=state.admin?'◇ Creator Admin':'◇ Creator mode';$('creatorMark').textContent=state.admin?'ADMIN':'';}catch(_){state.admin=false;}}
$('unlockAdmin')?.addEventListener('click',async()=>{const p=$('adminPassword').value.trim();if(!p)return;try{await api('/api/auth/admin/unlock',{method:'POST',body:JSON.stringify({password:p})});state.admin=true;$('adminPassword').value='';$('adminError').textContent='';closeModal('creatorModal');toast('Creator Admin unlocked.');await whoami();await loadSettings();}catch(e){$('adminError').textContent=e.message;}});

window.addEventListener('catalyst:avatar-ready',(e)=>{state.runtimeLive=!!e.detail?.live;$('studioRuntime')&&($('studioRuntime').textContent=state.runtimeLive?`3D body status: LIVE VRM 1.0 · ${Math.round(e.detail?.rigHeight||1.7*100)/100}m rig`:'3D body status: reference fallback');});
window.addEventListener('keydown',(e)=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('prompt')?.focus();}if(e.key==='Escape'&&state.audio)stopVoice();});

(async()=>{
  addWelcome();wireSuggestions();detectSpeechRecognition();await loadPrefs();await whoami();
  try{const d=await api('/api/dashboard');$('brainLabel').textContent=`Brain: ${d.brain?.model||'not configured'}`;}catch(_){}
  try{const a=await api('/api/avatar/state');state.appearance=a.appearance||state.prefs.appearance||'signature';state.expression=state.prefs.avatar_expression||'neutral';}catch(_){}
  try{await initCatalystVRM({containerId:'avatarWrap'});}catch(e){console.warn(e);}
  setCatalystMotionMode(state.motion);setCatalystExpression(state.expression);setCatalystAppearance(state.appearance);setCatalystGesture(state.gesture);
  setState('idle','Ready when you are.','neutral',false);renderLooks();renderLooks('studioLookGrid');renderExpressions();await loadRecentChats();wireSuggestions();
})();

window.showReasoning=()=>{page('missions');toast('Reasoning controls remain available through Catalyst missions and Creator settings.')};
window.showApexMissions=()=>{page('missions');toast('Apex missions opened.')};
