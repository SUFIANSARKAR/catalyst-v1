import os, shutil, subprocess
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SandboxResult:
    status:str; returncode:int|None; stdout:str; stderr:str; cwd:str; mode:str

class SandboxRunner:
    def __init__(self, workspace_root:str, data_root:str, mode='auto', docker_image='python:3.12-slim', timeout=120, memory_mb=2048, cpus=2.0, pids=256):
        self.workspace=Path(workspace_root).resolve(); self.data_root=Path(data_root).resolve(); self.mode=mode; self.docker_image=docker_image
        self.timeout=max(1,int(timeout)); self.memory_mb=max(256,int(memory_mb)); self.cpus=max(0.25,float(cpus)); self.pids=max(32,int(pids))
    def _docker(self): return shutil.which('docker')
    def _cwd(self, relative_cwd):
        cwd=(self.workspace/relative_cwd).resolve()
        if cwd!=self.workspace and self.workspace not in cwd.parents: raise PermissionError('Execution cwd escapes workspace')
        if not cwd.exists(): raise FileNotFoundError(relative_cwd)
        return cwd
    def run(self, command:str, relative_cwd='.'):
        cwd=self._cwd(relative_cwd); mode=self.mode
        if mode=='auto': mode='docker' if self._docker() else 'local'
        if mode=='off': return SandboxResult('disabled',None,'','Sandbox execution is disabled.',str(cwd),'off')
        if mode=='docker':
            docker=self._docker()
            if not docker: return SandboxResult('unavailable',None,'','Docker is not installed in this runtime.',str(cwd),'docker')
            rel=str(cwd.relative_to(self.workspace) if cwd!=self.workspace else '.')
            workdir=f'/workspace/{rel}' if rel!='.' else '/workspace'
            args=[docker,'run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                  '--pids-limit',str(self.pids),'--memory',f'{self.memory_mb}m','--cpus',str(self.cpus),
                  '--tmpfs','/tmp:rw,noexec,nosuid,size=256m','-v',f'{self.workspace}:/workspace:rw','-w',workdir,self.docker_image,'sh','-lc',command]
            try: cp=subprocess.run(args,text=True,capture_output=True,timeout=self.timeout)
            except subprocess.TimeoutExpired as e: return SandboxResult('timeout',None,(e.stdout or '')[-120000:],(e.stderr or '')[-60000:],str(cwd),'docker')
            return SandboxResult('completed' if cp.returncode==0 else 'failed',cp.returncode,cp.stdout[-120000:],cp.stderr[-60000:],str(cwd),'docker')
        env={k:v for k,v in os.environ.items() if k not in {'OPENAI_API_KEY','ANTHROPIC_API_KEY','GOOGLE_API_KEY','GEMINI_API_KEY'}}
        env['CATALYST_SANDBOX']='1'
        try: cp=subprocess.run(command,shell=True,cwd=cwd,text=True,capture_output=True,timeout=self.timeout,env=env)
        except subprocess.TimeoutExpired as e: return SandboxResult('timeout',None,(e.stdout or '')[-120000:],(e.stderr or '')[-60000:],str(cwd),'local')
        return SandboxResult('completed' if cp.returncode==0 else 'failed',cp.returncode,cp.stdout[-120000:],cp.stderr[-60000:],str(cwd),'local')
