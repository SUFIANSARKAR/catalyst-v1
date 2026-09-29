from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

class WorldModel:
    """Durable temporal knowledge graph using SQLite; relation versions preserve history rather than overwriting it."""
    def __init__(self,path='catalyst_data/world_model.db'):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(p,check_same_thread=False,timeout=30);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA busy_timeout=30000')
        self.db.execute('CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,type TEXT NOT NULL,name TEXT NOT NULL,attributes TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1)')
        self.db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_name_type ON entities(type,name)')
        self.db.execute('CREATE TABLE IF NOT EXISTS relations(id TEXT PRIMARY KEY,src TEXT NOT NULL,relation TEXT NOT NULL,dst TEXT NOT NULL,attributes TEXT NOT NULL,valid_from TEXT NOT NULL,valid_to TEXT,confidence REAL NOT NULL DEFAULT 1.0,source TEXT)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_rel_src ON relations(src,relation,valid_to)');self.db.execute('CREATE INDEX IF NOT EXISTS idx_rel_dst ON relations(dst,relation,valid_to)')
        self.db.commit()
    def upsert_entity(self,name,entity_type='concept',attributes=None):
        name=str(name).strip();
        if not name: raise ValueError('entity name is required')
        now=datetime.now(timezone.utc).isoformat();attrs=json.dumps(attributes or {},ensure_ascii=False);row=self.db.execute('SELECT id,attributes FROM entities WHERE type=? AND name=?',(entity_type,name)).fetchone()
        if row:
            old=json.loads(row['attributes'] or '{}');old.update(attributes or {});self.db.execute('UPDATE entities SET attributes=?,updated_at=?,active=1 WHERE id=?',(json.dumps(old,ensure_ascii=False),now,row['id']));self.db.commit();return row['id']
        eid=uuid4().hex;self.db.execute('INSERT INTO entities VALUES(?,?,?,?,?,?,1)',(eid,entity_type,name,attrs,now,now));self.db.commit();return eid
    def _entity_id(self,name):
        r=self.db.execute('SELECT id FROM entities WHERE name=? AND active=1 ORDER BY updated_at DESC LIMIT 1',(name,)).fetchone();return r['id'] if r else None
    def relate(self,src,relation,dst,attributes=None,confidence=1.0,source=None):
        sid=self.upsert_entity(src,'concept');did=self.upsert_entity(dst,'concept'); now=datetime.now(timezone.utc).isoformat();conf=max(0,min(1,float(confidence)))
        # Avoid endless duplicate active edges; update confidence/provenance by appending a version only when materially changed.
        current=self.db.execute('SELECT * FROM relations WHERE src=? AND relation=? AND dst=? AND valid_to IS NULL ORDER BY valid_from DESC LIMIT 1',(sid,relation,did)).fetchone()
        attrs=attributes or {}
        if current:
            cur_attrs=json.loads(current['attributes'] or '{}')
            cur_attrs.update(attrs)
            if float(current['confidence']) >= conf and cur_attrs==json.loads(current['attributes'] or '{}') and (source or '')==(current['source'] or ''): return current['id']
            self.db.execute('UPDATE relations SET valid_to=? WHERE id=?',(now,current['id']))
        rid=uuid4().hex;self.db.execute('INSERT INTO relations VALUES(?,?,?,?,?,?,?,?,?)',(rid,sid,relation,did,json.dumps(attrs,ensure_ascii=False),now,None,conf,source));self.db.commit();return rid
    def invalidate_relation(self,src,relation,dst,reason='',source='system'):
        sid=self._entity_id(src);did=self._entity_id(dst)
        if not sid or not did:return 0
        now=datetime.now(timezone.utc).isoformat();cur=self.db.execute('UPDATE relations SET valid_to=? WHERE src=? AND relation=? AND dst=? AND valid_to IS NULL',(now,sid,relation,did));
        if cur.rowcount: self.db.commit();return cur.rowcount
        return 0
    def ingest_memory(self,text,metadata=None,confidence=.7,source='memory'):
        meta=metadata or {}; entities=[str(e) for e in meta.get('entities',[]) if str(e).strip()]
        if not entities:
            import re;entities=list(dict.fromkeys(re.findall(r'\b[A-Z][A-Za-z0-9_-]{2,}\b',text)))[:20]
        for e in entities:self.upsert_entity(e,'concept')
        relations=meta.get('relations') or []
        if relations:
            for rel in relations:
                if isinstance(rel,dict) and rel.get('src') and rel.get('relation') and rel.get('dst'):
                    self.relate(rel['src'],rel['relation'],rel['dst'],rel.get('attributes') or {},rel.get('confidence',confidence),rel.get('source') or source)
        elif len(entities)>=2:
            for a,b in zip(entities,entities[1:]):self.relate(a,'co_occurs_with',b,{'memory':text[:500]},confidence,source)
        return {'entities':entities,'relations_added':len(relations) if relations else max(0,len(entities)-1)}
    def neighborhood(self,name,depth=2,limit=100):
        start=self._entity_id(name)
        if not start:return {'entity':None,'nodes':[],'edges':[]}
        seen={start};frontier=[start];edges=[]
        for _ in range(max(1,min(int(depth),5))):
            nxt=[]
            for eid in frontier:
                rows=self.db.execute('SELECT * FROM relations WHERE (src=? OR dst=?) AND valid_to IS NULL ORDER BY confidence DESC LIMIT ?',(eid,eid,limit)).fetchall()
                for r in rows:
                    other=r['dst'] if r['src']==eid else r['src'];
                    if other not in seen:seen.add(other);nxt.append(other)
                    edges.append(dict(r)|{'attributes':json.loads(r['attributes'] or '{}')})
            frontier=nxt
            if not frontier:break
        nodes=[]
        for eid in list(seen)[:limit]:
            r=self.db.execute('SELECT * FROM entities WHERE id=?',(eid,)).fetchone()
            if r:nodes.append(dict(r)|{'attributes':json.loads(r['attributes'] or '{}')})
        return {'entity':name,'nodes':nodes,'edges':edges[:limit]}
    def facts(self,entity=None,limit=100,include_history=False):
        args=[];q='SELECT r.*,s.name AS src_name,d.name AS dst_name FROM relations r JOIN entities s ON s.id=r.src JOIN entities d ON d.id=r.dst'
        where=[]
        if not include_history:where.append('r.valid_to IS NULL')
        if entity:
            eid=self._entity_id(entity)
            if not eid:return []
            where.append('(r.src=? OR r.dst=?)');args += [eid,eid]
        if where:q+=' WHERE '+' AND '.join(where)
        q+=' ORDER BY r.valid_from DESC LIMIT ?';args.append(max(1,min(int(limit),500)))
        rows=self.db.execute(q,args).fetchall();return [dict(r)|{'attributes':json.loads(r['attributes'] or '{}')} for r in rows]
    def search_entities(self,query,limit=25):
        q=f'%{str(query).strip()}%';rows=self.db.execute('SELECT * FROM entities WHERE name LIKE ? ORDER BY updated_at DESC LIMIT ?',(q,max(1,min(int(limit),100)))).fetchall();return [dict(r)|{'attributes':json.loads(r['attributes'] or '{}')} for r in rows]
    def close(self):self.db.close()
