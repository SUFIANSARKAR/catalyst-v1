import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

TERMINAL={'completed','failed','cancelled','rejected'}

class DeviceControlPlane:
    """Durable command/ack plane. Catalyst remains the authority; clients execute commands."""
    def __init__(self,path,registry):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(p,check_same_thread=False,timeout=30); self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=30000')
        self.db.execute('CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,device_id TEXT NOT NULL,action TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,requires_confirmation INTEGER NOT NULL,created_at TEXT NOT NULL,claimed_at TEXT,result TEXT,error TEXT,expires_at TEXT)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_commands_device_status ON commands(device_id,status,created_at)')
        self.db.commit(); self.registry=registry
    def issue(self,device_id,action,payload=None,requires_confirmation=True,ttl_seconds=300):
        d=self.registry.get(device_id)
        if not d: raise ValueError('Unknown device')
        if action not in d['capabilities']: raise ValueError(f'Device does not advertise capability: {action}')
        now=datetime.now(timezone.utc); cid=uuid4().hex
        exp=(now.timestamp()+max(1,int(ttl_seconds)))
        expires=datetime.fromtimestamp(exp,timezone.utc).isoformat()
        self.db.execute('INSERT INTO commands VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,device_id,action,json.dumps(payload or {}), 'pending',1 if requires_confirmation else 0,now.isoformat(),None,None,None,expires)); self.db.commit(); return self.get(cid)
    def claim(self,device_id):
        """Atomically claim the oldest live command for a device.

        Multiple polls can arrive concurrently (mobile + desktop + retries). The
        write lock makes selection and claim one operation so a command cannot be
        handed to two clients at once.
        """
        d=self.registry.get(device_id)
        if not d: raise ValueError('Unknown device')
        now=datetime.now(timezone.utc)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            while True:
                row=self.db.execute(
                    "SELECT * FROM commands WHERE device_id=? AND status='pending' ORDER BY created_at LIMIT 1",
                    (device_id,),
                ).fetchone()
                if not row:
                    self.db.commit(); return None
                if row['expires_at'] and datetime.fromisoformat(row['expires_at']) < now:
                    self.db.execute(
                        "UPDATE commands SET status='failed',error='command expired' WHERE id=? AND status='pending'",
                        (row['id'],),
                    )
                    continue
                changed=self.db.execute(
                    "UPDATE commands SET status='claimed',claimed_at=? WHERE id=? AND status='pending'",
                    (now.isoformat(),row['id']),
                ).rowcount
                if changed != 1:
                    continue
                self.db.commit()
                return self.get(row['id'])
        except Exception:
            self.db.rollback()
            raise
    def complete(self,cid,result=None): return self._finish(cid,'completed',result=result)
    def fail(self,cid,error): return self._finish(cid,'failed',error=str(error))
    def reject(self,cid,reason='rejected'): return self._finish(cid,'rejected',error=reason)
    def cancel(self,cid,reason='cancelled'): return self._finish(cid,'cancelled',error=reason)
    def get(self,cid):
        r=self.db.execute('SELECT * FROM commands WHERE id=?',(cid,)).fetchone(); return self._row(r) if r else None
    def device_id_for_command(self,cid):
        row=self.db.execute("SELECT device_id FROM commands WHERE id=?",(cid,)).fetchone()
        return row["device_id"] if row else None

    def list(self,device_id=None,status=None,limit=100):
        q='SELECT * FROM commands'; a=[]; where=[]
        if device_id: where.append('device_id=?'); a.append(device_id)
        if status: where.append('status=?'); a.append(status)
        if where:q+=' WHERE '+' AND '.join(where)
        q+=' ORDER BY created_at DESC LIMIT ?'; a.append(max(1,min(500,int(limit))))
        return [self._row(r) for r in self.db.execute(q,a).fetchall()]
    def _finish(self,cid,status,result=None,error=None):
        self.db.execute('UPDATE commands SET status=?,result=?,error=? WHERE id=? AND status NOT IN (\'completed\',\'failed\',\'cancelled\',\'rejected\')',(status,json.dumps(result) if result is not None else None,error,cid)); self.db.commit(); return self.get(cid)
    def _row(self,r):
        d=dict(r); d['payload']=json.loads(d['payload']); d['result']=json.loads(d['result']) if d['result'] else None; d['requires_confirmation']=bool(d['requires_confirmation']); return d
    def close(self):self.db.close()
