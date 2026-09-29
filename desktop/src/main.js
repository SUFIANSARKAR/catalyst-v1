import { invoke } from '@tauri-apps/api/core';

const root = document.querySelector('.shell');
root.innerHTML = `
  <header><div><h1>Catalyst</h1><p>Desktop companion · authenticated device bridge</p></div><span id="badge">OFFLINE</span></header>
  <section class="grid">
    <label>API URL<input id="url" value="http://127.0.0.1:8000"></label>
    <label>API token<input id="token" type="password" placeholder="optional for local server"></label>
    <label>Device name<input id="name" value="Catalyst Desktop"></label>
  </section>
  <div class="row"><button id="connect">Connect</button><button id="disconnect">Disconnect</button><button id="sys">System info</button></div>
  <pre id="log">Ready.</pre>
`;

const $ = (id) => document.getElementById(id);
let connected = false, deviceId = '', deviceToken = '', timer = null;
const log = (x) => $('log').textContent = typeof x === 'string' ? x : JSON.stringify(x, null, 2);

function headers(extra={}) {
  const h = { 'Accept': 'application/json', ...extra };
  if ($('token').value.trim()) h.Authorization = `Bearer ${$('token').value.trim()}`;
  if (deviceToken) h['X-Catalyst-Device-Token'] = deviceToken;
  return h;
}
async function api(path, opts={}) {
  const res = await fetch($('url').value.replace(/\/$/, '') + path, { ...opts, headers: headers(opts.headers || {}) });
  const text = await res.text();
  let data; try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${text.slice(0,800)}`);
  return data;
}

async function connect() {
  $('badge').textContent='CONNECTING';
  try {
    const body = { name:$('name').value.trim() || 'Catalyst Desktop', platform:'desktop-tauri', version:'5.6.0', capabilities:['open_url','open_file','show_notification','get_system_info'], metadata:{runtime:'tauri'} };
    const row = await api('/api/devices/register', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
    deviceId = row.id; deviceToken = row.device_token || '';
    if (!deviceToken) throw new Error('No device credential was provisioned. Re-register this client.');
    connected=true; $('badge').textContent='ONLINE'; log({connected:true,deviceId,capabilities:body.capabilities});
    clearInterval(timer); timer=setInterval(poll,2500); await poll();
  } catch(e) { connected=false; $('badge').textContent='ERROR'; log(e.message); }
}
function disconnect(){ connected=false; clearInterval(timer); timer=null; deviceId=''; deviceToken=''; $('badge').textContent='OFFLINE'; log('Disconnected.'); }

async function poll() {
  if (!connected) return;
  try {
    await api(`/api/devices/${deviceId}/heartbeat`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({metadata:{online:true}})});
    const cmd=await api(`/api/devices/${deviceId}/commands/claim`,{method:'POST'});
    if (!cmd || cmd.status==='empty') return;
    try {
      const result=await invoke('desktop_execute',{action:cmd.action,payload:cmd.payload||{}});
      await api(`/api/device-commands/${cmd.id}/complete`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(result)});
      log({command:cmd.action,result});
    } catch(e) {
      await api(`/api/device-commands/${cmd.id}/fail?error=${encodeURIComponent(e.message)}`,{method:'POST'});
      log({command:cmd.action,error:e.message});
    }
  } catch(e) { log(`Bridge error: ${e.message}`); }
}
$('connect').onclick=connect; $('disconnect').onclick=disconnect;
$('sys').onclick=async()=>{try{log(await invoke('desktop_execute',{action:'get_system_info',payload:{}}));}catch(e){log(e.message)}};
