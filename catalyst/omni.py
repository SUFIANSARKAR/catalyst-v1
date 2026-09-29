from __future__ import annotations
import base64, hashlib, json, os, platform, shutil, subprocess, time, webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .device.protocol import SUPPORTED_ACTIONS, READ_ONLY_ACTIONS
from .device.control import DeviceControlPlane


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventLedger:
    """Durable append-only event ledger used by cognition, devices and perception."""
    def __init__(self, path: str = "catalyst_data/events.db"):
        import sqlite3
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(p, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL, payload TEXT NOT NULL, fingerprint TEXT NOT NULL)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind,created_at)")
        self.db.commit()

    def emit(self, kind: str, source: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        fp = hashlib.sha256(f"{kind}\0{source}\0{raw}".encode()).hexdigest()
        eid = uuid4().hex
        self.db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)", (eid, utc_now(), kind, source, raw, fp))
        self.db.commit()
        return {"id": eid, "kind": kind, "source": source, "payload": payload}

    def recent(self, limit: int = 100, kind: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM events"; args: list[Any] = []
        if kind:
            q += " WHERE kind=?"; args.append(kind)
        q += " ORDER BY created_at DESC LIMIT ?"; args.append(max(1, min(int(limit), 500)))
        out=[]
        for row in self.db.execute(q,args).fetchall():
            d=dict(row)
            try:d["payload"]=json.loads(d["payload"])
            except Exception:pass
            out.append(d)
        return out
    def close(self): self.db.close()


class ObservationFusion:
    """Turns submitted observations into durable, timestamped perception records."""
    def __init__(self, events: EventLedger, perception=None, world_model=None, mind=None):
        self.events=events; self.perception=perception; self.world_model=world_model; self.mind=mind

    def ingest(self, *, source: str, modality: str, content: dict[str, Any], confidence: float = .7, session_id: str | None = None) -> dict[str, Any]:
        obs={"source":source,"modality":modality,"content":content,"confidence":max(0,min(1,float(confidence))),"session_id":session_id,"observed_at":utc_now()}
        event=self.events.emit("observation",source,obs)
        if self.perception:
            try:self.perception.add(modality,source,content,session_id=session_id)
            except TypeError:
                try:self.perception.add(source,modality,content)
                except Exception:pass
            except Exception:pass
        return {"event_id":event["id"],"observation":obs}

    def screen(self, source: str, image_path: str | None = None, text: str = "", app: str = "", url: str = "", confidence: float=.8, session_id: str|None=None):
        payload={"image_path":image_path,"text":text[:30000],"app":app[:200],"url":url[:1000]}
        return self.ingest(source=source,modality="screen",content=payload,confidence=confidence,session_id=session_id)

    def text(self, source: str, text: str, confidence: float=.9, session_id: str|None=None):
        return self.ingest(source=source,modality="text",content={"text":text[:30000]},confidence=confidence,session_id=session_id)

    def context(self, limit=30): return self.events.recent(limit=limit,kind="observation")


class HostDeviceExecutor:
    """Real local-shell executor for the Catalyst device protocol.

    It deliberately supports a finite action vocabulary instead of arbitrary shell input.
    Install this agent on the machine that should be controlled; Catalyst remains the
    command authority and this executor is only an actuator.
    """
    def __init__(self, workspace_root: str = "workspace", allow_destructive: bool = False):
        self.workspace=Path(workspace_root).resolve(); self.workspace.mkdir(parents=True,exist_ok=True)
        self.allow_destructive=allow_destructive

    @staticmethod
    def capabilities() -> list[str]: return sorted(SUPPORTED_ACTIONS)

    def _safe_workspace_file(self, value: str) -> Path:
        p=Path(value).expanduser()
        if not p.is_absolute(): p=self.workspace/p
        p=p.resolve()
        if p != self.workspace and self.workspace not in p.parents: raise PermissionError("File path escapes workspace")
        return p

    def _launch(self, target: str) -> dict[str, Any]:
        target=target.strip()
        if not target: raise ValueError("Missing launch target")
        common = {"xdg-open", "gio", "code", "cursor", "google-chrome", "chromium", "firefox", "nautilus", "explorer", "open"}
        executable=Path(target.split()[0]).name
        if executable not in common and not shutil.which(executable):
            raise PermissionError("Executable is not allowlisted or installed")
        args=target.split()
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return {"launched":args}

    def execute(self, action: str, payload: dict | None = None) -> dict[str, Any]:
        payload=payload or {}
        if action not in SUPPORTED_ACTIONS: raise ValueError("Unsupported action")
        start=time.perf_counter()
        if action=="get_system_info":
            result={"platform":platform.system(),"release":platform.release(),"machine":platform.machine(),"python":platform.python_version(),"cwd":str(Path.cwd()),"hostname":platform.node()}
        elif action=="open_url":
            url=str(payload.get("url","")).strip()
            if not (url.startswith("https://") or url.startswith("http://")): raise ValueError("Only http(s) URLs are supported")
            ok=webbrowser.open(url,new=2)
            result={"opened":bool(ok),"url":url}
        elif action=="open_file":
            p=self._safe_workspace_file(str(payload.get("path", "")))
            if not p.exists(): raise FileNotFoundError(str(p))
            opener=shutil.which("xdg-open") or shutil.which("open")
            if not opener: raise RuntimeError("No supported file opener installed")
            subprocess.Popen([opener,str(p)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            result={"opened":True,"path":str(p)}
        elif action in {"launch_app","focus_app"}:
            result=self._launch(str(payload.get("app") or payload.get("target") or ""))
            result["action"]=action
        elif action=="show_notification":
            title=str(payload.get("title","Catalyst"))[:200]; body=str(payload.get("body",""))[:1000]
            cmd=shutil.which("notify-send")
            if not cmd: raise RuntimeError("notify-send is not installed")
            subprocess.run([cmd,title,body],check=True,timeout=10)
            result={"notified":True,"title":title}
        elif action=="capture_screen":
            out=Path(str(payload.get("path") or (self.workspace/"catalyst_screen.png"))).expanduser().resolve()
            if out != self.workspace and self.workspace not in out.parents: raise PermissionError("Screenshot path escapes workspace")
            saved=False; methods=[]
            try:
                from PIL import ImageGrab
                img=ImageGrab.grab(); img.save(out); saved=True; methods.append("PIL.ImageGrab")
            except Exception: pass
            if not saved:
                cmd=shutil.which("gnome-screenshot") or shutil.which("scrot")
                if cmd:
                    subprocess.run([cmd,"-f",str(out)],check=True,timeout=20); saved=True; methods.append(Path(cmd).name)
            if not saved: raise RuntimeError("No usable screenshot backend on this device")
            data=out.read_bytes()
            result={"captured":True,"path":str(out),"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data),"backend":methods}
        elif action=="set_clipboard":
            text=str(payload.get("text",""))
            if shutil.which("xclip"):
                subprocess.run(["xclip","-selection","clipboard"],input=text.encode(),check=True,timeout=10)
            elif shutil.which("wl-copy"):
                subprocess.run(["wl-copy"],input=text.encode(),check=True,timeout=10)
            elif shutil.which("pbcopy"):
                subprocess.run(["pbcopy"],input=text.encode(),check=True,timeout=10)
            else: raise RuntimeError("No clipboard write backend installed")
            result={"set":True,"chars":len(text)}
        elif action=="get_clipboard":
            if shutil.which("xclip"):
                text=subprocess.check_output(["xclip","-o","-selection","clipboard"],timeout=10).decode(errors="replace")
            elif shutil.which("wl-paste"):
                text=subprocess.check_output(["wl-paste"],timeout=10).decode(errors="replace")
            elif shutil.which("pbpaste"):
                text=subprocess.check_output(["pbpaste"],timeout=10).decode(errors="replace")
            else: raise RuntimeError("No clipboard read backend installed")
            result={"text":text[:20000],"chars":len(text)}
        elif action in {"start_voice","stop_voice"}:
            # Native clients are expected to own the actual audio device. The host agent
            # can still report command receipt without pretending to control an unavailable mic.
            result={"requested":True,"action":action,"note":"Voice actuator delegated to native client."}
        elif action=="lock_device":
            if not self.allow_destructive: raise PermissionError("Device lock requires explicit local-agent enablement")
            cmd=shutil.which("loginctl")
            if cmd: subprocess.run([cmd,"lock-session"],check=True,timeout=10); result={"locked":True,"backend":"loginctl"}
            else: raise RuntimeError("No supported lock backend installed")
        else: raise RuntimeError("Action implementation missing")
        result.update({"ok":True,"elapsed_ms":round((time.perf_counter()-start)*1000,2)})
        return result


@dataclass
class DeviceAgentConfig:
    poll_seconds: float = 1.0
    ttl_seconds: int = 300


class DeviceAgent:
    """Poll/execute/ack native device agent against Catalyst's command plane."""
    def __init__(self, control: DeviceControlPlane, device_id: str, executor: HostDeviceExecutor, events: EventLedger, config: DeviceAgentConfig|None=None):
        self.control=control; self.device_id=device_id; self.executor=executor; self.events=events; self.config=config or DeviceAgentConfig()

    def run_once(self) -> dict[str, Any]:
        command=self.control.claim(self.device_id)
        if not command: return {"status":"idle"}
        if command.get("requires_confirmation"):
            self.control.reject(command["id"],"native agent requires a server-side approved command")
            return {"status":"rejected","command_id":command["id"]}
        try:
            result=self.executor.execute(command["action"],command.get("payload"))
            row=self.control.complete(command["id"],result)
            self.events.emit("device.result",self.device_id,{"command_id":command["id"],"action":command["action"],"result":result})
            return {"status":"completed","command":row}
        except Exception as exc:
            row=self.control.fail(command["id"],str(exc))
            self.events.emit("device.error",self.device_id,{"command_id":command["id"],"action":command["action"],"error":str(exc)})
            return {"status":"failed","command":row,"error":str(exc)}


class UnifiedCognition:
    """Cross-system capability fusion: objective, memory, situation and execution evidence."""
    def __init__(self, gateway=None, mind=None, cognitive_state=None, situational=None, executive=None, adaptive=None, events=None):
        self.gateway=gateway; self.mind=mind; self.state=cognitive_state; self.situational=situational; self.executive=executive; self.adaptive=adaptive; self.events=events or EventLedger()

    def snapshot(self, query: str = "") -> dict[str, Any]:
        data={"timestamp":utc_now(),"query":query,"memory":[],"state":None,"situation":{},"objectives":[],"events":self.events.recent(30)}
        if self.mind:
            try:data["memory"]=self.mind.search(query,20) if query else self.mind.active(20)
            except Exception:pass
        if self.state:
            try:data["state"]=self.state.context(20)
            except Exception:pass
        if self.situational:
            try:data["situation"]=self.situational.context()
            except Exception:pass
        if self.executive:
            try:data["objectives"]=self.executive.rank_objectives(20)
            except Exception:pass
        return data

    def deliberate(self, objective: str, context: dict | None=None, candidates: list[str]|None=None) -> dict[str, Any]:
        context=context or self.snapshot(objective)
        candidates=candidates or ["continue current mission", "investigate evidence before acting", "ask for approval", "delegate to a specialist"]
        ranked=[]
        for c in candidates:
            score=.5
            lc=c.lower()
            if "investigate" in lc: score+=.12
            if "specialist" in lc and context.get("memory"): score+=.08
            if "approval" in lc: score+=.05
            if "continue" in lc and context.get("objectives"): score+=.08
            ranked.append({"candidate":c,"score":round(min(score,1),3)})
        ranked.sort(key=lambda x:x["score"],reverse=True)
        result={"objective":objective,"candidates":ranked,"selected":ranked[0]["candidate"],"context":context}
        self.events.emit("cognition.deliberation","unified_cognition",result)
        return result

    def capability_fusion(self) -> dict[str, Any]:
        return {
            "reasoning": True, "persistent_memory": bool(self.mind), "working_memory": True,
            "world_model": True, "perception": True, "situational_intelligence": bool(self.situational),
            "adaptive_missions": bool(self.adaptive), "executive": bool(self.executive),
            "event_ledger": True, "device_control": True,
        }

class CognitiveDeliberator:
    """Model-assisted executive deliberation with a deterministic fallback.

    The model proposes; the surrounding Catalyst policy/mission system decides what can execute.
    """
    def __init__(self, gateway, events): self.gateway=gateway; self.events=events

    def propose(self, objective: str, context: dict[str, Any], max_steps: int = 12) -> dict[str, Any]:
        max_steps=max(1,min(int(max_steps),24))
        if self.gateway and getattr(self.gateway,'active_profile',None):
            prompt={"objective":objective,"context":context,"constraints":{"max_steps":max_steps,"no_secret_access":True,"no_policy_bypass":True,"no_unapproved_consequential_actions":True}}
            try:
                msg=self.gateway.chat([
                    {'role':'system','content':'You are Catalyst\'s executive planner. Build a concrete, verifiable plan. Separate observations from assumptions. Return JSON only with keys: intent, risks, steps. Each step must contain id, action, purpose, verification.'},
                    {'role':'user','content':json.dumps(prompt,ensure_ascii=False)}
                ],None,.1,task='planning')
                raw=str(msg.get('content') or '').strip(); start=raw.find('{'); end=raw.rfind('}')
                if start>=0 and end>start:
                    data=json.loads(raw[start:end+1])
                    steps=data.get('steps') if isinstance(data,dict) else None
                    if isinstance(steps,list):
                        data['steps']=steps[:max_steps]
                        for i,step in enumerate(data['steps'],1):
                            if not isinstance(step,dict): data['steps'][i-1]={'id':f's{i}','action':str(step),'purpose':'planned action','verification':'explicit result required'}
                        result={'status':'model_proposed','plan':data}
                        self.events.emit('cognition.plan','deliberator',result); return result
            except Exception as exc:
                model_error=str(exc)
            else: model_error=''
        else: model_error='no model provider configured'
        plan={'intent':objective,'risks':['insufficient evidence','permission/approval boundary'],'steps':[{'id':'s1','action':'observe','purpose':'refresh environment and relevant memory','verification':'fresh evidence recorded'},{'id':'s2','action':'prepare','purpose':'construct a bounded plan','verification':'plan contains explicit checks'},{'id':'s3','action':'execute_permitted_step','purpose':'perform only permitted work','verification':'tool/device result acknowledged'},{'id':'s4','action':'reconcile','purpose':'update mind with outcome','verification':'outcome stored'}]}
        result={'status':'fallback_proposed','plan':plan,'model_error':model_error}
        self.events.emit('cognition.plan','deliberator',result); return result


class VoiceTurnManager:
    """Turns completed audio into a durable cognitive turn using existing AudioEngine."""
    def __init__(self, audio, sessions, mind=None, events=None): self.audio=audio; self.sessions=sessions; self.mind=mind; self.events=events or EventLedger()
    def transcribe_and_remember(self, audio_path: str, session_id: str | None=None, provider: str|None=None, language: str|None=None):
        result=self.audio.transcribe(audio_path,provider=provider,language=language)
        text=str(result.get('text') or '').strip()
        if session_id and text and self.sessions:
            try:self.sessions.append(session_id,'user',text,{'voice':True,'provider':result.get('provider'),'model':result.get('model')})
            except Exception:pass
        if self.mind and text:
            try:self.mind.remember('episode',f'Voice turn: {text[:1000]}',source='voice',confidence=.78,importance=.6,metadata={'session_id':session_id,'provider':result.get('provider')})
            except Exception:pass
        event=self.events.emit('voice.transcription','voice',{'session_id':session_id,'text':text[:10000],'provider':result.get('provider')})
        return {'event_id':event['id'],'transcription':result}
    def speak(self,text: str, provider: str|None=None, voice: str|None=None): return self.audio.synthesize(text,provider=provider,voice=voice)


class EngineeringWorkflowPlanner:
    """Engineering workflow brain: plan → inspect → choose specialist → define verification."""
    DOMAINS={'cfd','fluid','thermal','heat','structural','mechanical','geometry','mesh','weather','geophysics','additive','optimization','simulation'}
    def __init__(self, catalog, events): self.catalog=catalog; self.events=events
    def plan(self, objective: str) -> dict[str, Any]:
        tokens={x.lower() for x in objective.replace('/',' ').split() if len(x)>2}
        domains=[x for x in self.DOMAINS if x in tokens]
        rec=self.catalog.find_for_domain(objective)
        steps=[{'id':'s1','kind':'classify','action':'classify engineering objective','verification':'domain selected'}, {'id':'s2','kind':'inspect','action':'inspect available geometry/data','verification':'dataset metadata captured'}]
        if any(d in domains for d in {'cfd','fluid','thermal','structural','simulation'}):
            steps.append({'id':'s3','kind':'physics_ai','action':'select PhysicsNeMo-compatible workflow and model family','verification':'model/runtime/inputs explicitly identified'})
        steps += [{'id':f's{len(steps)+1}','kind':'analyze','action':'run bounded engineering analysis','verification':'numerical/artifact output recorded'},{'id':f's{len(steps)+2}','kind':'validate','action':'check assumptions, units, boundary conditions, and result consistency','verification':'validation report recorded'}]
        out={'protocol':'catalyst.engineering.workflow.v1','objective':objective,'detected_domains':domains,'recommended_sources':rec[:4],'steps':steps}
        self.events.emit('engineering.plan','engineering',out); return out
