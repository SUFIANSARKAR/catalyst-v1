from __future__ import annotations
import base64, json, re, sqlite3, threading, time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None


@dataclass
class BrowserObservation:
    session_id: str
    url: str
    title: str
    screenshot: str | None
    viewport: dict[str, int]
    visible_text: str
    links: list[dict[str, str]]
    timestamp: str
    step: int
    page_state: dict[str, Any]


class ComputerUsePolicy:
    SAFE_ACTIONS = {"wait", "click", "type", "press", "scroll", "navigate", "back", "forward", "reload"}
    DESTRUCTIVE_TEXT = re.compile(r"\b(delete|remove|purchase|buy|send|publish|transfer|pay|shutdown|format|submit|confirm)\b", re.I)

    def __init__(self, allowed_domains: list[str] | None = None, max_actions: int = 80):
        self.allowed_domains = {d.lower().lstrip('.') for d in (allowed_domains or []) if d.strip()}
        self.max_actions = max(1, int(max_actions))

    def validate(self, action: dict[str, Any], action_count: int = 0) -> tuple[bool, str]:
        if action_count >= self.max_actions:
            return False, "computer-use action budget exhausted"
        kind = str(action.get("action", "")).lower()
        if kind not in self.SAFE_ACTIONS:
            return False, f"unsupported computer-use action: {kind}"
        if kind == "navigate":
            url = str(action.get("url", ""))
            p = urlparse(url)
            if p.scheme not in {"http", "https"} or not p.hostname:
                return False, "navigation requires a public http(s) URL"
            if self.allowed_domains and p.hostname.lower() not in self.allowed_domains and not any(p.hostname.lower().endswith('.' + d) for d in self.allowed_domains):
                return False, f"domain not allowed: {p.hostname}"
        if kind == "click":
            has_coords = action.get("x") is not None and action.get("y") is not None
            if not has_coords and not action.get("selector"):
                return False, "click requires selector or both x and y"
        if kind in {"type", "press"} and self.DESTRUCTIVE_TEXT.search(str(action.get("text", ""))):
            return False, "destructive-looking input requires explicit approval"
        return True, "ok"


class BrowserSessionStore:
    """Durable browser-session metadata. Live Playwright handles remain in-process."""
    def __init__(self, path: str = 'catalyst_data/computer_sessions.db'):
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(p, check_same_thread=False, timeout=30); self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,url TEXT NOT NULL,status TEXT NOT NULL,action_count INTEGER NOT NULL DEFAULT 0,metadata TEXT NOT NULL DEFAULT \'{}\')')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_browser_sessions_updated ON sessions(updated_at)')
        self.db.commit()
    def create(self, sid, url, metadata=None):
        now=datetime.now(timezone.utc).isoformat(); self.db.execute('INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?,?)',(sid,now,now,url,'active',0,json.dumps(metadata or {},ensure_ascii=False))); self.db.commit()
    def update(self, sid, url=None, status=None, action_count=None, metadata=None):
        row=self.get(sid)
        if not row: return None
        self.db.execute('UPDATE sessions SET updated_at=?,url=COALESCE(?,url),status=COALESCE(?,status),action_count=COALESCE(?,action_count),metadata=COALESCE(?,metadata) WHERE id=?',(datetime.now(timezone.utc).isoformat(),url,status,action_count,json.dumps(metadata,ensure_ascii=False) if metadata is not None else None,sid)); self.db.commit(); return self.get(sid)
    def get(self,sid):
        r=self.db.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
        if not r:return None
        x=dict(r); x['metadata']=json.loads(x['metadata'] or '{}'); return x
    def recent(self,limit=50):
        rows=self.db.execute('SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?',(max(1,min(int(limit),200)),)).fetchall();out=[]
        for r in rows:
            x=dict(r);x['metadata']=json.loads(x['metadata'] or '{}');out.append(x)
        return out
    def close(self,sid): self.update(sid,status='closed')
    def close_all(self): self.db.execute("UPDATE sessions SET status='closed',updated_at=? WHERE status='active'",(datetime.now(timezone.utc).isoformat(),)); self.db.commit()
    def shutdown(self): self.close_all(); self.db.close()


class PlaywrightComputerUse:
    """Real browser actuator with bounded actions, persisted session metadata, and evidence snapshots."""
    def __init__(self, data_root: str = "catalyst_data", policy: ComputerUsePolicy | None = None, headless: bool = True):
        self.root = Path(data_root) / "computer_use"; self.root.mkdir(parents=True, exist_ok=True)
        self.policy = policy or ComputerUsePolicy(); self.headless = bool(headless)
        self.sessions = BrowserSessionStore(Path(data_root) / 'computer_sessions.db')
        self._lock = threading.RLock(); self._pw = None; self._browser = None; self._contexts = {}; self._pages = {}; self._counts = {}

    def _ensure_runtime(self):
        if sync_playwright is None: raise RuntimeError("Playwright is not installed. Install it and a Chromium browser before using computer use.")
        if self._pw is None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self.headless)

    def start(self, url='about:blank', viewport=None, metadata=None):
        with self._lock:
            self._ensure_runtime(); sid=uuid4().hex; vp=viewport or {'width':1440,'height':900}
            context=self._browser.new_context(viewport=vp); page=context.new_page(); self._contexts[sid]=context; self._pages[sid]=page; self._counts[sid]=0
            if url != 'about:blank':
                ok,reason=self.policy.validate({'action':'navigate','url':url})
                if not ok: context.close(); self._contexts.pop(sid,None); self._pages.pop(sid,None); self._counts.pop(sid,None); raise PermissionError(reason)
                page.goto(url,wait_until='domcontentloaded',timeout=30000)
            self.sessions.create(sid,page.url,metadata or {})
            return sid

    def observe(self, session_id, step=0):
        page=self._page(session_id); stamp=datetime.now(timezone.utc).isoformat(); shot=self.root/f'{session_id}_{int(time.time()*1000)}.png'; page.screenshot(path=str(shot),full_page=False)
        try: visible=page.locator('body').inner_text(timeout=3000)[:50000]
        except Exception: visible=''
        links=[]
        try:
            for a in page.locator('a').all()[:80]:
                txt=(a.inner_text(timeout=500) or '').strip()[:160]; href=a.get_attribute('href') or ''
                if txt or href: links.append({'text':txt,'href':href})
        except Exception: pass
        vp=page.viewport_size or {'width':1440,'height':900}; state={'ready_state':page.evaluate('document.readyState'),'action_count':self._counts.get(session_id,0),'host':urlparse(page.url).hostname,'session_status':'active'}
        obs=BrowserObservation(session_id,page.url,page.title()[:300],str(shot),vp,visible,links,stamp,step,state)
        self.sessions.update(session_id,url=page.url,action_count=self._counts.get(session_id,0))
        return obs

    def observation_payload(self, obs):
        raw=Path(obs.screenshot).read_bytes() if obs.screenshot else b''
        return {'observation':asdict(obs),'screenshot_base64':base64.b64encode(raw).decode('ascii') if raw else None}

    def act(self, session_id, action, require_approval=True, approved=False):
        with self._lock:
            count=self._counts.get(session_id,0); ok,reason=self.policy.validate(action,count)
            if not ok:return {'status':'blocked','reason':reason,'action':action}
            if require_approval and not approved:return {'status':'approval_required','reason':'computer-use execution requires explicit approval','action':action}
            kind=str(action['action']).lower(); page=self._page(session_id)
            try:
                if kind=='navigate': page.goto(str(action['url']),wait_until='domcontentloaded',timeout=30000)
                elif kind=='click':
                    if action.get('selector'): page.locator(str(action['selector'])).first.click(timeout=10000)
                    else:
                        x=float(action['x']); y=float(action['y']); vp=page.viewport_size or {'width':1440,'height':900}
                        if x<0 or y<0 or x>vp['width'] or y>vp['height']: return {'status':'blocked','reason':'coordinates outside viewport','action':action}
                        page.mouse.click(x,y)
                elif kind=='type':
                    text=str(action.get('text','')); sel=action.get('selector'); page.locator(str(sel)).first.fill(text) if sel else page.keyboard.type(text)
                elif kind=='press': page.keyboard.press(str(action.get('key',action.get('text','Enter'))))
                elif kind=='scroll': page.mouse.wheel(float(action.get('dx',0)),float(action.get('dy',600)))
                elif kind=='back': page.go_back(wait_until='domcontentloaded',timeout=20000)
                elif kind=='forward': page.go_forward(wait_until='domcontentloaded',timeout=20000)
                elif kind=='reload': page.reload(wait_until='domcontentloaded',timeout=20000)
                elif kind=='wait': time.sleep(max(0,min(float(action.get('seconds',1)),10)))
                self._counts[session_id]=count+1; obs=self.observe(session_id,self._counts[session_id]); self.sessions.update(session_id,url=obs.url,action_count=self._counts[session_id]);
                return {'status':'ok','action':action,'observation':asdict(obs)}
            except Exception as exc:
                self.sessions.update(session_id,status='error',action_count=count)
                return {'status':'error','action':action,'error':str(exc)}

    def close(self,session_id):
        with self._lock:
            ctx=self._contexts.pop(session_id,None); self._pages.pop(session_id,None); self._counts.pop(session_id,None)
            if ctx:
                try:ctx.close()
                except Exception:pass
            self.sessions.close(session_id)
    def recent_sessions(self,limit=50): return self.sessions.recent(limit)
    def close_all(self):
        with self._lock:
            for sid in list(self._contexts): self.close(sid)
            if self._pw:
                try:self._pw.stop()
                except Exception:pass
            self._pw=None;self._browser=None;self.sessions.shutdown()
    def _page(self,sid):
        page=self._pages.get(sid)
        if page is None: raise KeyError(f'Unknown browser session: {sid}')
        return page


class ComputerUsePlanner:
    SYSTEM="""You are Catalyst's computer-use action planner. Return ONLY valid JSON with keys: action, rationale, selector, x, y, text, key, url, dx, dy, seconds. Choose exactly one action from wait, click, type, press, scroll, navigate, back, forward, reload. Never claim success. Never perform or propose destructive transactions such as purchases, deletion, sending, publishing, payments, transfers, account changes, or confirmation. Prefer selector-based actions when reliable; otherwise use screenshot coordinates within the viewport. The executor and approval layer enforce permissions."""
    def __init__(self,gateway): self.gateway=gateway
    def choose_action(self,observation,goal=''):
        payload=asdict(observation);payload['goal']=goal
        if observation.screenshot:
            raw=Path(observation.screenshot).read_bytes();payload['screenshot_base64']=base64.b64encode(raw).decode('ascii')
        messages=[{'role':'system','content':self.SYSTEM},{'role':'user','content':[{'type':'text','text':json.dumps(payload,ensure_ascii=False)},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+payload['screenshot_base64']}}]}]
        msg=self.gateway.chat(messages,None,0.1,task='computer_use'); content=(msg.get('content') or '').strip()
        if content.startswith('```'): content=content.split('\n',1)[1].rsplit('```',1)[0]
        action=json.loads(content)
        if not isinstance(action,dict) or not action.get('action'): raise ValueError('Invalid computer-use action')
        return action
