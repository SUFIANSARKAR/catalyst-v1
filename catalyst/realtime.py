from __future__ import annotations
import base64, json, time, threading
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

@dataclass
class RealtimeSession:
    id: str
    session_id: str | None
    status: str
    codec: str
    sample_rate: int
    started_at: float
    updated_at: float
    chunks: int = 0
    bytes_received: int = 0
    metadata: dict = field(default_factory=dict)

class RealtimeVoiceStore:
    """Durable-ish realtime transport state; audio bytes are stored as bounded append-only chunks.
    Model/provider work remains delegated to the configured AudioEngine, avoiding undocumented vendor protocols.
    """
    def __init__(self, root='catalyst_data/realtime_voice', max_session_bytes=50_000_000):
        self.root=Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.max_session_bytes=max(1,int(max_session_bytes)); self._lock=threading.RLock(); self._sessions={}
    def create(self, session_id=None, codec='audio/webm', sample_rate=16000, metadata=None):
        with self._lock:
            rid=uuid4().hex; now=time.time()
            self._sessions[rid]=RealtimeSession(rid,session_id,'open',codec,int(sample_rate),now,now,metadata=dict(metadata or {}))
            (self.root/f'{rid}.bin').touch()
            self._write_meta(rid)
            return self.get(rid)
    def append(self,rid,data:bytes):
        with self._lock:
            s=self._sessions[rid]
            if s.status!='open': raise RuntimeError('Realtime session is not open')
            if s.bytes_received+len(data)>self.max_session_bytes: raise ValueError('Realtime session byte limit exceeded')
            with (self.root/f'{rid}.bin').open('ab') as f: f.write(data)
            s.chunks+=1; s.bytes_received+=len(data); s.updated_at=time.time(); self._write_meta(rid); return self.get(rid)
    def close(self,rid,status='closed'):
        with self._lock:
            s=self._sessions[rid]; s.status=status; s.updated_at=time.time(); self._write_meta(rid); return self.get(rid)
    def get(self,rid):
        with self._lock:
            s=self._sessions.get(rid)
            if not s: return None
            return {k:(v if not isinstance(v,dict) else dict(v)) for k,v in s.__dict__.items()}
    def audio_path(self,rid):
        if rid not in self._sessions: raise KeyError(rid)
        return self.root/f'{rid}.bin'
    def list(self,limit=50):
        with self._lock: return [self.get(x) for x in list(self._sessions)[-max(1,min(int(limit),100)):][::-1]]
    def ingest(self,rid, data, encoding='base64'):
        raw=base64.b64decode(data) if encoding=='base64' else data.encode() if isinstance(data,str) else data
        return self.append(rid,raw)
    def _write_meta(self,rid):
        (self.root/f'{rid}.json').write_text(json.dumps(self.get(rid),indent=2),encoding='utf-8')
    def shutdown(self):
        with self._lock:
            for rid,s in self._sessions.items():
                if s.status=='open': s.status='abandoned'; s.updated_at=time.time(); self._write_meta(rid)
