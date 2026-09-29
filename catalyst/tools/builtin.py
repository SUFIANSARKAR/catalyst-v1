import json,subprocess,socket,ipaddress
from urllib.parse import urlparse
import httpx
from .base import Tool,ToolRegistry
from .safe_paths import WorkspaceGuard
from ..analysis import DataAnalysisEngine
from ..research import ResearchEngine
from ..projects.compiler import ProjectMemoryCompiler
from ..tasks.store import TaskStore
from ..agents.adapters import default_adapters

def _public_url(url):
    u=urlparse(url)
    if u.scheme not in {'http','https'} or not u.hostname:raise ValueError('Only http(s) URLs are allowed')
    for item in socket.getaddrinfo(u.hostname,None):
        a=ipaddress.ip_address(item[4][0])
        if any((a.is_private,a.is_loopback,a.is_link_local,a.is_reserved,a.is_multicast)):raise PermissionError('Blocked private/loopback network target')

def build_tools(workspace,allow_shell=False,analysis_engine=None,research=None,compiler=None,tasks=None,agent_executor=None):
    r=ToolRegistry()
    def read_file(path):
        p=workspace.resolve(path);return p.read_text(encoding='utf-8',errors='replace')[:500000]
    def list_files(path='.'):
        p=workspace.resolve(path);return [str(x.relative_to(workspace.root)) for x in sorted(p.rglob('*')) if x.is_file()][:5000]
    def write_file(path,content):
        p=workspace.resolve(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf-8');return f'wrote {p.relative_to(workspace.root)}'
    def web_fetch(url):
        _public_url(url);resp=httpx.get(url,follow_redirects=True,timeout=30);resp.raise_for_status();return resp.text[:300000]
    r.register(Tool('read_file','Read a text file inside the workspace.',{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},read_file))
    r.register(Tool('list_files','List workspace files.',{'type':'object','properties':{'path':{'type':'string'}},'required':[]},list_files))
    r.register(Tool('write_file','Write a text file. Requires approval.',{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']},write_file,True))
    r.register(Tool('web_fetch','Fetch a public web page.',{'type':'object','properties':{'url':{'type':'string'}},'required':['url']},web_fetch))
    if analysis_engine:
        r.register(Tool('index_project','Index workspace files into a persistent chunk index.',{'type':'object','properties':{},'required':[]},analysis_engine.index_project))
        r.register(Tool('search_project','Search indexed project content and return the most relevant chunks.',{'type':'object','properties':{'query':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':30}},'required':['query']},analysis_engine.search))
        r.register(Tool('analyze_file','Profile CSV, JSON, or text/code without placing an entire dataset in context.',{'type':'object','properties':{'relative_path':{'type':'string'},'max_rows':{'type':'integer','minimum':10,'maximum':100000}},'required':['relative_path']},analysis_engine.analyze_file))
    if research:
        r.register(Tool('web_search','Search the public web and return ranked result URLs.',{'type':'object','properties':{'query':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':20}},'required':['query']},research.search))
        r.register(Tool('research_sources','Search, fetch, and persist a small research packet with source URLs.',{'type':'object','properties':{'query':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':8}},'required':['query']},research.research))
    if compiler:
        r.register(Tool('compile_project_memory','Compile readable project memory files: overview, architecture, decisions, experiments, failures, manifest.',{'type':'object','properties':{'project_name':{'type':'string'}},'required':[]},compiler.compile))
    if tasks:
        r.register(Tool('create_task','Create a persistent engineering/research task in the Catalyst queue.',{'type':'object','properties':{'title':{'type':'string'},'description':{'type':'string'},'agent':{'type':'string'},'priority':{'type':'integer'}},'required':['title']},tasks.create))
        r.register(Tool('list_tasks','List queued/running/completed Catalyst tasks.',{'type':'object','properties':{'status':{'type':'string'}},'required':[]},tasks.list))
    if agent_executor:
        def delegate(tasks_list, max_workers=4):
            return agent_executor.run(tasks_list, max_workers=max_workers, synthesize=True)
        r.register(Tool('delegate_agents','Delegate bounded work to configured specialist agents and synthesize their results.',{'type':'object','properties':{'tasks_list':{'type':'array','items':{'type':'object'}},'max_workers':{'type':'integer','minimum':1,'maximum':16}},'required':['tasks_list']},delegate,True))
    if allow_shell:
        def shell(command):
            cp=subprocess.run(command,shell=True,cwd=workspace.root,capture_output=True,text=True,timeout=90);return json.dumps({'returncode':cp.returncode,'stdout':cp.stdout[-120000:],'stderr':cp.stderr[-60000:]})
        r.register(Tool('shell','Run a bounded shell command inside the workspace. Requires approval.',{'type':'object','properties':{'command':{'type':'string'}},'required':['command']},shell,True))
    return r
