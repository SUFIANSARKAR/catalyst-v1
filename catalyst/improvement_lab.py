from __future__ import annotations
import hashlib, json, shutil, subprocess, tempfile, time
from pathlib import Path
from uuid import uuid4

class ImprovementLab:
    """Safe self-improvement workflow: proposal -> isolated experiment -> benchmark -> explicit promotion/rollback.
    No production code is changed until promote() is explicitly called.
    """
    def __init__(self, root='.', data_root='catalyst_data/improvement_lab'):
        self.root=Path(root).resolve(); self.data=Path(data_root).resolve();
        # Never place experiment storage inside the source tree: that would recursively copy the lab into itself.
        if self.data == self.root or self.root in self.data.parents:
            self.data=self.root.parent/f'.{self.root.name}-improvement-lab'
        self.data.mkdir(parents=True,exist_ok=True)
    def create(self, title, patch='', test_command='python -m pytest -q', reason='', baseline_command='python -m pytest -q'):
        eid=uuid4().hex; sandbox=self.data/eid/'sandbox'; sandbox.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(self.root,sandbox,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.git','catalyst_data','__pycache__','.pytest_cache','*.pyc','*.db'))
        meta={'id':eid,'title':title,'reason':reason,'patch':patch,'test_command':test_command,'baseline_command':baseline_command,'status':'created','sandbox':str(sandbox),'created_at':time.time()}
        (sandbox.parent/'experiment.json').write_text(json.dumps(meta,indent=2),encoding='utf-8'); return meta
    def _validate_patch(self, patch):
        for line in patch.splitlines():
            if line.startswith(('--- ','+++ ')):
                raw=line[4:].split('\t',1)[0].strip()
                if raw in {'/dev/null','dev/null'}: continue
                raw=raw[2:] if raw.startswith(('a/','b/')) else raw
                p=Path(raw)
                if p.is_absolute() or '..' in p.parts:
                    raise ValueError(f'Unsafe patch path: {raw}')
    def _apply_patch(self, cwd, patch_file):
        if not patch_file.exists(): return
        patch_text=patch_file.read_text(encoding='utf-8')
        self._validate_patch(patch_text)
        attempts=[]
        if (Path(cwd)/'.git').exists():
            attempts.append(['git','apply','--whitespace=nowarn',str(patch_file)])
        else:
            # GitHub Codespaces and slim containers may not ship GNU patch.
            # --no-index applies a standard unified diff without requiring a
            # repository, while still preserving Git's path safety checks.
            attempts.append(['git','apply','--no-index','--whitespace=nowarn',str(patch_file)])
        attempts.extend([['patch','-p1','--forward','-i',str(patch_file)],['patch','-p0','--forward','-i',str(patch_file)]])
        last='';
        for cmd in attempts:
            cp=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=120); last=cp.stderr or cp.stdout
            if cp.returncode==0:return
        raise RuntimeError(last[-12000:] or 'Patch application failed')
    def _run_command(self, command, cwd, timeout):
        started=time.perf_counter(); cp=subprocess.run(command,cwd=cwd,shell=True,text=True,capture_output=True,timeout=timeout)
        return {'status':'passed' if cp.returncode==0 else 'failed','returncode':cp.returncode,'duration_seconds':round(time.perf_counter()-started,3),'stdout':cp.stdout[-50000:],'stderr':cp.stderr[-30000:]}
    def run(self,eid,timeout=1200):
        meta=self._load(eid); sandbox=Path(meta['sandbox'])
        if meta.get('patch'):
            patch=sandbox.parent/'candidate.patch'; patch.write_text(meta['patch'],encoding='utf-8')
            try:self._apply_patch(sandbox,patch)
            except Exception as exc:
                meta.update(status='patch_rejected',error=str(exc)); self._save(meta); return meta
        baseline=self._run_command(meta.get('baseline_command') or meta['test_command'],self.root,timeout)
        candidate=self._run_command(meta['test_command'],sandbox,timeout)
        meta.update(status='passed' if baseline['status']=='passed' and candidate['status']=='passed' else 'failed',baseline=baseline,candidate=candidate,returncode=candidate['returncode'],duration_seconds=candidate['duration_seconds'],stdout=candidate['stdout'],stderr=candidate['stderr'],candidate_hash=self._tree_hash(sandbox),finished_at=time.time())
        meta['regression_gate']={'baseline_status':baseline['status'],'candidate_status':candidate['status'],'passed':baseline['status']=='passed' and candidate['status']=='passed'}
        self._save(meta); return meta
    def promote(self,eid):
        meta=self._load(eid)
        if meta.get('status')!='passed': raise RuntimeError('Only a passed experiment can be promoted')
        sandbox=Path(meta['sandbox']); patch=meta.get('patch','')
        if not patch: raise RuntimeError('Experiment has no patch to promote')
        backup=self.data/meta['id']/f'production-backup-{int(time.time())}'
        backup.parent.mkdir(parents=True,exist_ok=True); shutil.copytree(self.root,backup,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.git','catalyst_data','__pycache__','.pytest_cache','*.pyc','*.db'))
        p=self.data/meta['id']/'promote.patch'; p.write_text(patch,encoding='utf-8')
        try:
            self._apply_patch(self.root,p)
        except Exception as exc:
            meta.update(status='promotion_failed',promotion_error=str(exc)); self._save(meta); raise
        meta.update(status='promoted',backup=str(backup),promoted_at=time.time()); self._save(meta); return meta
    def rollback(self,eid):
        meta=self._load(eid); backup=Path(meta.get('backup',''))
        if not backup.exists(): raise RuntimeError('No production backup available')
        # Restore only source/config files captured by the backup; keep runtime data outside the backup.
        for item in backup.iterdir():
            target=self.root/item.name
            if item.name in {'catalyst_data','.git','proposals'}: continue
            if target.exists() and target.is_dir(): shutil.rmtree(target)
            elif target.exists(): target.unlink()
            if item.is_dir(): shutil.copytree(item,target)
            else: shutil.copy2(item,target)
        meta.update(status='rolled_back',rolled_back_at=time.time()); self._save(meta); return meta
    def recent(self,limit=50):
        out=[]
        for p in sorted(self.data.glob('*/experiment.json'),key=lambda x:x.stat().st_mtime,reverse=True)[:max(1,min(int(limit),100))]:
            try: out.append(json.loads(p.read_text(encoding='utf-8')))
            except Exception: pass
        return out
    def _load(self,eid):
        p=self.data/eid/'experiment.json';
        if not p.exists(): raise KeyError(eid)
        return json.loads(p.read_text(encoding='utf-8'))
    def _save(self,meta): (self.data/meta['id']/'experiment.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    def _tree_hash(self,root):
        h=hashlib.sha256()
        for p in sorted(root.rglob('*')):
            if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts:
                h.update(str(p.relative_to(root)).encode()); h.update(p.read_bytes())
        return h.hexdigest()
