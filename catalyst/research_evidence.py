from __future__ import annotations
import hashlib, json, re, time
from pathlib import Path
from collections import Counter
from .research import ResearchEngine

class EvidenceResearchEngine:
    """Evidence-first research layer over Catalyst's existing public-web collector.
    Keeps source provenance, stable hashes, extracted claims/snippets and simple contradiction signals.
    """
    def __init__(self, base:ResearchEngine, root='catalyst_data/evidence', gateway=None):
        self.base=base; self.gateway=gateway; self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    @staticmethod
    def _norm(text): return re.sub(r'\s+',' ',text or '').strip()
    @staticmethod
    def _terms(text):
        return [x.lower() for x in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text or '') if x.lower() not in {'that','this','with','from','have','were','which','about','their','there','would','could'}]
    def _fingerprint(self,source): return hashlib.sha256(self._norm(source.get('content','')).encode()).hexdigest()
    def _snippets(self,content,query,max_snippets=4):
        terms=set(self._terms(query)); sentences=re.split(r'(?<=[.!?])\s+',self._norm(content)); scored=[]
        for s in sentences:
            score=sum(1 for t in terms if t in s.lower())
            if score: scored.append((score,len(s),s[:1200]))
        scored.sort(reverse=True); return [s for _,_,s in scored[:max_snippets]]
    def research(self,query,limit=6,provider=None):
        raw=self.base.research(query,limit=limit)
        sources=[]
        for s in raw.get('sources',[]):
            item={'title':s.get('title','Source'),'url':s.get('url',''),'status':s.get('status'),'error':s.get('error'),
                  'content_sha256':self._fingerprint(s),'snippets':self._snippets(s.get('content',''),query)}
            sources.append(item)
        claims=self._derive_claims(query,sources)
        report={'protocol':'catalyst.evidence.v1','query':query,'created_at':time.time(),'provider':provider or 'default','sources':sources,'claims':claims,'contradictions':self._contradictions(claims)}
        p=self.root/f'evidence-{int(time.time()*1000)}.json'; p.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8'); report['artifact']=str(p)
        if self.gateway and getattr(self.gateway,'active_profile',None) and self.gateway.active_profile.configured:
            try:
                context='\n'.join(f"[{i+1}] {x.get('title','Source')}: {x.get('url','')}\n\n"+'\n'.join(x.get('snippets',[])) for i,x in enumerate(sources))
                prompt=("You are Catalyst's evidence analyst. Answer the research question using ONLY the evidence below.\n"
                        f"Question: {query}\n\nEvidence:\n{context[:50000]}\n\n"
                        "Return a concise conclusion, key claims, uncertainties, and cite source numbers like [1]. Do not invent facts.")
                answer=self.gateway.chat([{'role':'system','content':'Evidence must be grounded in supplied sources.'},{'role':'user','content':prompt}],task='research')
                report['analysis']=answer
            except Exception as exc:
                report['analysis_error']=str(exc)
        return report
    def _derive_claims(self,query,sources):
        claims=[]
        for s in sources:
            for snippet in s.get('snippets',[]):
                key=' '.join(self._terms(snippet)[:24]);
                claims.append({'id':hashlib.sha1((s['content_sha256']+key).encode()).hexdigest()[:16],'source_url':s['url'],'text':snippet,'terms':self._terms(snippet)[:32]})
        return claims
    def _contradictions(self,claims):
        # Conservative heuristic: flag paired claims sharing many topic terms but containing opposing lexical markers/numbers.
        out=[]; opposites=[('increase','decrease'),('higher','lower'),('yes','no'),('true','false'),('supports','opposes'),('before','after')]
        for i,a in enumerate(claims):
            for b in claims[i+1:]:
                if a['source_url']==b['source_url']: continue
                overlap=len(set(a['terms']) & set(b['terms']))
                if overlap<2: continue
                la=a['text'].lower(); lb=b['text'].lower(); hit=next(((x,y) for x,y in opposites if (x in la and y in lb) or (y in la and x in lb)),None)
                if hit or (re.search(r'\b\d+(?:\.\d+)?\b',la) and re.search(r'\b\d+(?:\.\d+)?\b',lb)):
                    out.append({'claim_a':a['id'],'claim_b':b['id'],'reason':'lexical-opposition-or-conflicting-numeric-evidence','signals':hit})
        return out[:50]
