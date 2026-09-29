from pathlib import Path
from datetime import datetime, timezone
import json
import secrets
from fastapi import FastAPI,HTTPException,Request,UploadFile,File,WebSocket,WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse,StreamingResponse,JSONResponse,RedirectResponse
from pydantic import BaseModel,Field
from ..config import Settings,ProviderProfile
from ..providers import ModelGateway
from ..memory import MemoryStore
from ..sessions import SessionStore
from ..analysis import DataAnalysisEngine
from ..tools.safe_paths import WorkspaceGuard
from ..tools.builtin import build_tools
from ..agents import AgentRegistry
from ..agents.executor import AgentExecutionManager
from ..core import Catalyst
from ..projects.compiler import ProjectMemoryCompiler
from ..tasks.store import TaskStore
from ..audit.store import AuditStore
from ..research import ResearchEngine
from ..automation import AutomationStore
from ..export import ExportManager
from ..jobs.store import JobStore
from ..jobs.worker import JobWorker
from ..jobs.handlers import JobHandlers
from ..provenance.store import ProvenanceStore
from ..analysis.artifacts import ArtifactStore
from ..data.inspector import DatasetInspector
from ..plugins import Plugin,PluginRegistry
from ..data import AnalysisWorkbench
from ..attachments import AttachmentStore
from ..approvals import ApprovalStore
from ..missions import MissionStore
from ..health import HealthRegistry
from ..observability import ObservabilityStore
from ..cognitive import CognitiveStateStore
from ..improvement import ImprovementManager
from ..security import PolicyEngine, Principal
from ..evals import EvaluationHarness
from ..media import MediaEngine, MediaJobError
from ..media.planner import CreativePlanner
from ..media.production import MediaProductionPipeline
from ..media.quality import MediaQualityController
from ..media.studio import MediaStudio
from ..engineering.mission import EngineeringMissionController
from ..capabilities import manifest
from ..integrations import IntegrationFabric
from ..version import __version__, __title__, __description__
from ..audio import AudioEngine
from ..memory.semantic import SemanticMemoryBridge
from ..world_model import WorldModel
from ..perception import PerceptionStore
from ..computer_use import PlaywrightComputerUse, ComputerUsePolicy, ComputerUsePlanner
from ..memory.working import WorkingMemory
from ..mind import CatalystMind
from ..long_horizon import LongHorizonEvaluator
from ..teams import TeamEngine
from ..identity_auth import IdentityAuthority, AuthResult
from ..realtime import RealtimeVoiceStore
from ..persona import load_persona
from ..providers.realtime import RealtimeProviderBridge
from ..research_evidence import EvidenceResearchEngine
from ..improvement_lab import ImprovementLab
from ..device import DeviceRegistry, ShellBridge, DeviceControlPlane
from ..proactive import SituationalStore, SituationalEngine
from ..engineering import EngineeringIntelligenceFabric, EngineeringCatalog
from ..executive import CognitiveExecutive
from ..autonomy import AutonomousCognition, AutonomousCognitionDaemon
from ..monster import CatalystMonster, MonsterConfig
from ..apex import ApexMissionStore
from ..adaptive import AdaptiveMissionController
from ..durability import DurabilityManager
from ..learning import LearningLedger
from ..omni import EventLedger, ObservationFusion, HostDeviceExecutor, UnifiedCognition, DeviceAgent, CognitiveDeliberator, VoiceTurnManager, EngineeringWorkflowPlanner
from ..avatar import APPEARANCES, AvatarController, load_avatar_manifest, avatar_runtime_info
from ..ui_preferences import UIPreferences

class ChatRequest(BaseModel): message:str=Field(min_length=1); session_id:str|None=None; attachments:list[str]=Field(default_factory=list)
class AdminUnlockRequest(BaseModel): password:str=Field(min_length=1,max_length=256)
class LocalSignupRequest(BaseModel): username:str=Field(min_length=1,max_length=64); password:str=Field(min_length=8,max_length=256)
class LocalLoginRequest(BaseModel): username:str=Field(min_length=1,max_length=64); password:str=Field(min_length=1,max_length=256)
class ProfileRequest(BaseModel): name:str; base_url:str; model:str; api_key:str; kind:str='openai_compatible'; capabilities:list[str]=Field(default_factory=list); role:str='general'; options:dict=Field(default_factory=dict)
class TaskRequest(BaseModel): title:str; description:str=''; agent:str='general'; priority:int=50
class AutomationRequest(BaseModel): name:str; objective:str; interval_minutes:int=60
class JobRequest(BaseModel): kind:str='general'; payload:dict={}; max_attempts:int=2
class DeviceRegisterRequest(BaseModel): name:str; platform:str; version:str=''; capabilities:list[str]=Field(default_factory=list); metadata:dict=Field(default_factory=dict); device_id:str|None=None
class DeviceHeartbeatRequest(BaseModel): metadata:dict=Field(default_factory=dict)
class SuggestionStatusRequest(BaseModel): status:str
class MonsterMissionRequest(BaseModel): objective:str=Field(min_length=1); execute:bool=False; approval:bool=False
class LocalModelRequest(BaseModel): base_url:str='http://127.0.0.1:11434/v1'; model:str=''; timeout:float=180.0
class ReasoningRequest(BaseModel): objective:str=Field(min_length=1); use_model:bool=True

class MediaGenerateRequest(BaseModel):
    prompt:str=Field(min_length=1)
    provider:str|None=None
    references:list[str]=Field(default_factory=list)
    aspect_ratio:str='16:9'
    quality:str='auto'
    background:str='auto'
    variants:int=1
    negative_prompt:str=''
    size:str|None=None
    output_compression:int|None=None
    duration:int=8
    resolution:str='720p'
    audio:bool=True
    fps:int|None=None
    seed:int|None=None
    options:dict=Field(default_factory=dict)

class MediaEditRequest(BaseModel):
    operation:str
    inputs:list[str]=Field(default_factory=list)
    options:dict=Field(default_factory=dict)

settings=Settings(); memory=MemoryStore(settings.memory_path); sessions=SessionStore(); workspace=WorkspaceGuard(settings.workspace_root)
analysis=DataAnalysisEngine(settings.workspace_root,settings.data_root); research=ResearchEngine(settings.data_root)
compiler=ProjectMemoryCompiler(settings.workspace_root,'catalyst_data/memory'); tasks=TaskStore('catalyst_data/tasks.db'); audit=AuditStore('catalyst_data/audit.db')
automation=AutomationStore('catalyst_data/automations.db'); jobs=JobStore('catalyst_data/jobs.db'); provenance=ProvenanceStore('catalyst_data/provenance.db'); artifacts=ArtifactStore('catalyst_data/artifacts'); attachments=AttachmentStore(settings.data_root); approvals=ApprovalStore('catalyst_data/approvals.db'); missions=MissionStore('catalyst_data/missions.db'); health=HealthRegistry(); observability=ObservabilityStore('catalyst_data/observability.db'); improvements=ImprovementManager('.'); policy=PolicyEngine(); identity=IdentityAuthority(settings,policy); evals=EvaluationHarness('catalyst_data/evals'); media=MediaEngine(settings,artifacts,attachments,audit)
gateway=ModelGateway(settings, observability); audio=AudioEngine(settings,gateway,artifacts,attachments); semantic=SemanticMemoryBridge(memory,gateway,settings); long_horizon=LongHorizonEvaluator(); persona=load_persona(); realtime_voice=RealtimeVoiceStore(settings.data_root + '/realtime_voice'); realtime_bridge=RealtimeProviderBridge(gateway); evidence_research=EvidenceResearchEngine(research,gateway=gateway); improvement_lab=ImprovementLab('.')
mind=CatalystMind(settings.mind_path,memory); mind.ensure_core_identity(); durability=DurabilityManager(settings.data_root,settings.memory_path,settings.mind_path); learning=LearningLedger(Path(settings.data_root)/'learning.db'); cognitive_state=CognitiveStateStore(settings.cognitive_state_path); world_model=WorldModel(settings.world_model_path); perception=PerceptionStore(settings.perception_path); devices=DeviceRegistry('catalyst_data/devices.db'); shell_bridge=ShellBridge(devices); device_control=DeviceControlPlane('catalyst_data/device_commands.db',devices); situational_store=SituationalStore('catalyst_data/situational.db'); situational=SituationalEngine(situational_store,world_model,missions,automation,devices); engineering=EngineeringIntelligenceFabric(settings.workspace_root,settings.data_root); monster=CatalystMonster(settings.workspace_root,gateway=gateway,config=MonsterConfig(data_root=settings.data_root,reasoning_mode=settings.reasoning_mode,reasoning_model_calls=settings.reasoning_model_calls)); computer_use=PlaywrightComputerUse(settings.data_root,ComputerUsePolicy(settings.computer_use_allowed_domains,settings.computer_use_max_actions),headless=settings.computer_use_headless); computer_planner=ComputerUsePlanner(gateway); working_memory=WorkingMemory(Path(settings.data_root)/'working_memory.json',settings.working_memory_chars); creative_planner=CreativePlanner(gateway); media_pipeline=MediaProductionPipeline(media,creative_planner); media_quality=MediaQualityController(); media_studio=MediaStudio(media_pipeline,media_quality); engineering_missions=EngineeringMissionController(engineering.repository, engineering.test_strategy); agents=AgentRegistry(); team_engine=TeamEngine(gateway,agents,settings,audit); integrations=IntegrationFabric(settings); plugins=PluginRegistry(); plugins.register(Plugin('core','Catalyst core capabilities',enabled=True,trusted=True))
inspector=DatasetInspector(settings.workspace_root); workbench=AnalysisWorkbench(settings.workspace_root,settings.data_root)
agent_executor=AgentExecutionManager(agents,settings.workspace_root,settings.data_root,audit,settings,gateway,integrations)
tools=build_tools(workspace,settings.allow_shell,analysis,research,compiler,tasks,agent_executor)
catalyst=Catalyst(gateway,memory,tools,agents,settings,sessions,analysis,tasks,audit,compiler,research,automation,agent_executor,attachments,approvals,semantic,world_model,working_memory,computer_use,perception,situational,mind,learning)
from ..cognitive import CognitiveLoop
catalyst.cognitive_loop=CognitiveLoop(mind,catalyst.knowledge,working_memory,cognitive_state,situational,world_model)
executive=CognitiveExecutive('catalyst_data/executive.db',cognitive_state,mind,situational,missions); autonomy=AutonomousCognition('catalyst_data/autonomy.db',executive,mind,cognitive_state,situational,missions,jobs,settings.autonomous_cognition_max_cycles); adaptive=AdaptiveMissionController('catalyst_data/adaptive_missions.db',missions,jobs,mind,cognitive_state,situational,gateway,getattr(settings,'adaptive_max_recoveries',3),getattr(settings,'adaptive_stall_seconds',900)); avatar_controller=AvatarController(); ui_preferences=UIPreferences(Path(settings.data_root) / 'ui_preferences.json'); events=EventLedger('catalyst_data/events.db'); observations=ObservationFusion(events,perception,world_model,mind); host_executor=HostDeviceExecutor(settings.workspace_root); unified=UnifiedCognition(gateway,mind,cognitive_state,situational,executive,adaptive,events); deliberator=CognitiveDeliberator(gateway,events); voice_turns=VoiceTurnManager(audio,sessions,mind,events); engineering_planner=EngineeringWorkflowPlanner(EngineeringCatalog,events); autonomy_daemon=AutonomousCognitionDaemon(autonomy,settings.autonomous_cognition_poll_seconds,settings.autonomous_cognition_enabled)
job_worker=JobWorker(jobs,JobHandlers(catalyst,analysis,compiler,agent_executor,provenance,artifacts,missions,media),settings.automation_poll_seconds,automation)
job_worker.start(); autonomy_daemon.start()

# Proactive scanning is intentionally conservative: it records signals/suggestions but does not execute actions.
def _proactive_loop():
    import time
    while True:
        try: situational.scan()
        except Exception: pass
        time.sleep(settings.proactive_scan_seconds)
import threading
threading.Thread(target=_proactive_loop, daemon=True, name='catalyst-proactive').start()

app=FastAPI(title=f'{__title__} API',version=__version__,description=__description__); app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins,allow_methods=['*'],allow_headers=['*'])

def _self_heal_plan(error_text: str):
    """Deterministic self-heal suggestions for common runtime errors.

    This does NOT claim to have fixed anything; it returns a bounded plan.
    """
    import re
    text=(error_text or '').strip()
    category='unknown'
    if re.search(r"(ModuleNotFoundError|ImportError)", text, re.I):
        category='dependency-or-import'
    elif re.search(r"(SyntaxError|IndentationError)", text, re.I):
        category='syntax'
    elif re.search(r"(AssertionError|FAILED|test_.*failed)", text, re.I):
        category='test-regression'
    elif re.search(r"(Timeout|timed out|deadline|ReadTimeout)", text, re.I):
        category='timeout'
    elif re.search(r"(PermissionError|permission denied)", text, re.I):
        category='permissions'
    elif re.search(r"(401|403|Authentication required|Invalid username or password)", text, re.I):
        category='auth'
    elif re.search(r"(429|rate limit|RateLimit)", text, re.I):
        category='rate-limit'
    elif re.search(r"(No configured .* provider|No model configured|No configured image generation provider)", text, re.I):
        category='missing-provider'

    actions=[
        'capture the exact error text and the endpoint/action that produced it',
        'classify the failure (auth vs provider vs dependency vs timeout)',
        'apply the smallest safe fix',
        'retry once and confirm the error is gone',
    ]
    if category=='missing-provider':
        actions=[
            'Open ⚙ Models & API in the UI',
            'Click “Use DeepSeek (recommended)”, paste your API key, Save provider, then Switch',
            'Retry the same request',
        ]
    elif category=='dependency-or-import':
        actions=[
            'Confirm the missing module name from the error',
            'Install it in the Catalyst environment (pip install <module>)',
            'Restart the server and retry',
        ]
    elif category=='timeout':
        actions=[
            'Retry once (transient timeouts happen)',
            'If it repeats: lower parallelism and/or increase CATALYST_TIMEOUT',
            'For media jobs: reduce resolution/duration or run fewer concurrent shots',
        ]
    elif category in {'auth','rate-limit'}:
        actions=[
            'Confirm you are logged in (Account → Log in / Sign up)',
            'If admin-required: unlock Creator Admin once (Admin button)',
            'If rate-limited: wait briefly, then retry; consider using a fallback provider',
        ]

    return {'protocol':'catalyst.self_heal.v1','category':category,'error':text[:20000],'actions':actions}

@app.middleware('http')
async def security_gate(request: Request, call_next):
    if request.url.path.startswith('/api/'):
        path=request.url.path
        # Sign-in/bootstrap endpoints must remain reachable before authentication.
        if path in {'/api/auth/admin/unlock','/api/auth/google/start','/api/auth/google/callback'}:
            return await call_next(request)
        auth=request.headers.get('authorization','')
        supplied=auth[7:] if auth.lower().startswith('bearer ') else request.headers.get('x-catalyst-token','')
        supplied=supplied or request.cookies.get('catalyst_session','')
        enabled=bool(getattr(settings,'api_token','') or getattr(settings,'api_tokens',{}))
        if enabled:
            result=identity.authenticate(supplied, request.headers.get(getattr(settings,'auth_subject_header','x-catalyst-subject'),'creator'))
            admin=identity.require_admin(supplied)
            if not result.authenticated and not admin:
                return __import__('fastapi').responses.JSONResponse({'detail':'Authentication required'},status_code=401)
            request.state.principal=Principal(subject='admin',role='creator') if admin else result.principal
            request.state.admin=admin
        else:
            result=identity.authenticate(supplied, 'creator') if supplied else AuthResult(False,Principal(subject='anonymous',role='guest'))
            request.state.principal=Principal(subject='creator',role='creator') if not result.authenticated else result.principal
            request.state.admin=identity.require_admin(supplied)
    return await call_next(request)

def _principal(request: Request):
    return getattr(request.state,'principal',Principal(subject='creator',role='creator'))

def _require(request: Request, capability: str):
    # Privileged capabilities are deliberately bound to the explicit Creator
    # Admin session, not merely to the default local principal.
    privileged = {'write','shell','delegate','automation','approval','model','admin','audio','improvement','device','perception'}
    if getattr(settings, 'enhanced_admin_only', True) and capability in privileged and not getattr(request.state, 'admin', False):
        raise HTTPException(status_code=403, detail='Creator Admin mode is required for enhanced Catalyst capabilities.')
    try:
        policy.require(_principal(request), capability)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

def _require_admin_mode(request: Request):
    if getattr(settings, 'enhanced_admin_only', True) and not getattr(request.state, 'admin', False):
        raise HTTPException(status_code=403, detail='Creator Admin mode is required for Enhanced Catalyst.')

@app.get('/api/auth/whoami')
def auth_whoami(request:Request):
    p=_principal(request); token=request.cookies.get('catalyst_session','') or request.headers.get('x-catalyst-token','')
    return {'subject':p.subject,'role':p.role,'admin':bool(getattr(request.state,'admin',False)),'authenticated':p.role != 'guest' or bool(token),'identity':identity.describe()}

@app.post('/api/auth/admin/unlock')
def auth_admin_unlock(req:AdminUnlockRequest, request:Request):
    token=identity.unlock_admin(req.password, subject=_principal(request).subject if _principal(request).role!='guest' else 'creator')
    if not token: raise HTTPException(status_code=401, detail='That admin password was not accepted.')
    response=JSONResponse({'ok':True,'subject':'Creator','role':'creator','admin':True,'message':'Creator access unlocked.'})
    response.set_cookie('catalyst_session',token,max_age=settings.admin_session_ttl,httponly=True,samesite='lax',secure=request.url.scheme=='https',path='/')
    return response

@app.post('/api/auth/logout')
def auth_logout(request:Request):
    token=request.cookies.get('catalyst_session',''); identity.logout(token)
    response=JSONResponse({'ok':True}); response.delete_cookie('catalyst_session',path='/'); return response

@app.post('/api/auth/local/signup')
def auth_local_signup(req:LocalSignupRequest, request:Request):
    """Create a local account (personal deployments)."""
    try:
        identity.create_local_user(req.username, req.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {'ok': True, 'username': req.username}

@app.post('/api/auth/local/login')
def auth_local_login(req:LocalLoginRequest, request:Request):
    token=identity.authenticate_local_user(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail='Invalid username or password')
    response=JSONResponse({'ok':True,'subject':req.username,'role':'guest','admin':False,'message':'Signed in.'})
    response.set_cookie('catalyst_session',token,max_age=86400,httponly=True,samesite='lax',secure=request.url.scheme=='https',path='/')
    return response

@app.get('/api/auth/google/start')
def auth_google_start(request:Request):
    redirect_uri=settings.google_redirect_uri or str(request.base_url).rstrip('/')+'/api/auth/google/callback'
    try: url=identity.start_google(redirect_uri)
    except ValueError as exc: raise HTTPException(status_code=503,detail=str(exc))
    return RedirectResponse(url)

@app.get('/api/auth/google/callback')
def auth_google_callback(request:Request, code:str|None=None, state:str|None=None):
    if not code or not state: raise HTTPException(status_code=400,detail='Missing Google OAuth callback parameters.')
    try: token=identity.consume_google_callback(code,state)
    except Exception as exc: raise HTTPException(status_code=401,detail=f'Google sign-in failed: {exc}')
    response=RedirectResponse('/')
    response.set_cookie('catalyst_session',token,max_age=86400,httponly=True,samesite='lax',secure=request.url.scheme=='https',path='/')
    return response

@app.get('/api/dashboard')
def dashboard():
    p=gateway.active_profile
    obs=observability.summary()
    return {'version':__version__,'brain':{'provider':p.name if p else None,'model':p.model if p else None,'configured':bool(p and p.configured),'capabilities':list(p.capabilities) if p else []},'workspace':{'root':str(workspace.root),'indexed_chunks':len(analysis.search('',50))},'counts':{'sessions':len(sessions.list(1000)),'tasks':len(tasks.list()),'jobs':len(jobs.list()),'missions':len(missions.list()),'automations':len(automation.list()),'attachments':len([x for x in attachments.root.iterdir() if x.is_file()]),'artifacts':len(artifacts.list())},'observability':obs,'agents':agents.describe(),'integrations':integrations.describe(),'health':health.report(),'perception_observations':len(perception.recent(500)),'world_facts':len(world_model.facts(limit=500)),'devices':len(devices.list()),'pending_suggestions':len(situational_store.list_suggestions('pending',500)),'mind':mind.stats(),'cognitive_state':cognitive_state.stats()}

@app.get('/api/capabilities')
def capabilities(): return manifest(settings,gateway,tools,agents,plugins,media,job_worker,policy,audio,identity)

@app.get('/api/memory/stats')
def memory_stats():
    try:
        return memory.stats()
    except AttributeError:
        return {'backend':'sqlite','status':'available'}

@app.get('/api/mind/stats')
def mind_stats(): return mind.stats()

@app.get('/api/catalyst/state')
def catalyst_state():
    """Single read-only state surface for the Catalyst command deck."""
    profile = gateway.active_profile
    situation = situational.context()
    return {
        'identity': {'name': persona.name, 'presentation': persona.presentation, 'voice': persona.voice_preset},
        'loop': ['understand', 'recall', 'plan', 'approve', 'act', 'verify', 'report', 'remember'],
        'brain': {'provider': profile.name if profile else None, 'model': profile.model if profile else None, 'configured': bool(profile and profile.configured)},
        'memory': mind.stats(),
        'learning': learning.self_evaluation(),
        'durability': durability.status(),
        'focus': situation.get('focus', {}),
        'signals': situation.get('signals', [])[:6],
        'suggestions': situation.get('suggestions', [])[:6],
        'safety': {'policy': 'governed', 'execution': 'approval-gated', 'verification': 'required'},
    }

@app.post('/api/mind/backup')
def mind_backup(request: Request):
    _require_admin_mode(request)
    return {'ok': True, 'backup': durability.snapshot(), 'status': durability.status()}

@app.post('/api/mind/export')
def mind_export(request: Request):
    _require_admin_mode(request)
    return {'ok': True, 'export': durability.export_memory_json(), 'status': durability.status()}

@app.get('/api/mind/durability')
def mind_durability(): return durability.status()

@app.get('/api/catalyst/learning/stats')
def catalyst_learning_stats(): return learning.stats()

@app.get('/api/catalyst/learning/evaluation')
def catalyst_learning_evaluation(): return learning.self_evaluation()

@app.get('/api/catalyst/learning/search')
def catalyst_learning_search(q: str, limit: int = 8): return learning.search(q, max(1, min(limit, 50)))

@app.get('/api/cognitive/state')
def cognitive_state_stats(): return cognitive_state.stats()

@app.get('/api/cognitive/context')
def cognitive_context(): return {'context':cognitive_state.context(20),'objectives':cognitive_state.active_objectives(20),'episodes':cognitive_state.recent_episodes(12)}

@app.get('/api/cognition/pulse')
def cognition_pulse():
    """Bounded, read-only snapshot for the command-deck UI.

    This composes persisted state only. Refreshing the dashboard never invokes
    a model and never dispatches an action.
    """
    profile = gateway.active_profile
    try:
        reasoning = monster.reasoning.memory.recent(6)
    except Exception:
        reasoning = []
    try:
        mission_rows = monster.apex.store.list(None, 6)
    except Exception:
        mission_rows = []
    return {
        'version': __version__,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'brain': {
            'provider': profile.name if profile else None,
            'model': profile.model if profile else None,
            'configured': bool(profile and profile.configured),
            'capabilities': list(profile.capabilities) if profile else [],
        },
        'provider_health': gateway.health(),
        'mind': mind.stats(),
        'cognitive': cognitive_state.stats(),
        'objectives': cognitive_state.active_objectives(6),
        'reasoning': reasoning,
        'missions': mission_rows,
        'signals': situational_store.list_signals(6),
    }

@app.post('/api/cognitive/objectives')
def cognitive_objective(req: dict, request:Request):
    _require_admin_mode(request)
    title=str(req.get('title','')).strip()
    if not title: raise HTTPException(400,'title is required')
    oid=cognitive_state.objective(title,str(req.get('status','active')),float(req.get('priority',.7)),req.get('metadata') or {})
    return {'id':oid,'status':'active'}

@app.post('/api/cognitive/objectives/{objective_id}')
def cognitive_objective_update(objective_id:str, req:dict, request:Request):
    _require_admin_mode(request)
    if not cognitive_state.update_objective(objective_id,str(req.get('status','active'))): raise HTTPException(404,'Unknown objective')
    return {'ok':True,'id':objective_id,'status':req.get('status')}


@app.get('/api/autonomy/stats')
def autonomy_stats(): return autonomy.stats()
@app.get('/api/autonomy/runs')
def autonomy_runs(limit:int=50): return autonomy.recent(limit)
@app.post('/api/autonomy/cycle')
def autonomy_cycle(payload:dict|None=None):
    payload=payload or {}
    return autonomy.run_once(payload.get('objective_id'),catalyst,dispatch=bool(payload.get('dispatch',settings.autonomous_cognition_auto_dispatch)))


@app.get('/api/adaptive/stats')
def adaptive_stats(): return adaptive.stats()
@app.get('/api/adaptive/runs')
def adaptive_runs(limit:int=50): return adaptive.recent(limit)
@app.post('/api/adaptive/supervise')
def adaptive_supervise(request:Request, limit:int=25):
    _require(request,'automation')
    return {'adaptations':adaptive.supervise_once(limit)}

@app.get('/api/executive/stats')
def executive_stats(): return {'stats':executive.stats(),'ranked_objectives':executive.rank_objectives(10)}

@app.get('/api/executive/cycles')
def executive_cycles(limit:int=20): return executive.recent_cycles(limit)

@app.post('/api/executive/cycle')
def executive_cycle(req:dict, request:Request):
    _require(request,'automation')
    return executive.prepare_cycle(catalyst, req.get('objective_id'))

@app.post('/api/executive/decisions')
def executive_decision(req:dict, request:Request):
    _require(request,'automation')
    return {'decision_id':executive.record_decision(req.get('objective_id'),req.get('title',''),req.get('choice',''),req.get('rationale',''),req.get('evidence') or [],req.get('confidence',.7),req.get('status','accepted'))}

@app.get('/api/mind/search')
def mind_search(q:str,limit:int=24): return mind.search(q,max(1,min(limit,100)))

@app.get('/api/mind/context')
def mind_context(q:str,limit:int=24): return {'query':q,'context':mind.build_context(q,max(1,min(limit,50)))}

@app.delete('/api/mind/{memory_id}')
def mind_forget(memory_id:str):
    if not mind.forget(memory_id): raise HTTPException(404,'Unknown cognitive memory')
    return {'ok':True,'forgotten':memory_id}

@app.get('/api/status')
def status():
    p=gateway.active_profile
    return {'version':__version__,'mission':'general AI and tool creation/improvement','model':p.model if p else None,'provider':p.name if p else None,'workspace':str(workspace.root),'tools':len(tools.list()),'agents':agents.describe(),'tasks':len(tasks.list()),'plugins':plugins.list(),'job_worker':bool(job_worker.thread and job_worker.thread.is_alive()),'policy_roles':policy.describe(),'mind':mind.stats(),'cognitive_state':cognitive_state.stats()}
@app.get('/api/memory/search')
def memory_search(q:str,limit:int=12):
    return memory.search(q, max(1,min(limit,50)))

@app.post('/api/memory/consolidate')
def memory_consolidate(limit:int=500):
    return memory.consolidate(max(50,min(limit,2000)))

@app.get('/api/memory/{memory_id}')
def memory_get(memory_id:int):
    row=memory.get(memory_id)
    if not row: raise HTTPException(404,'Unknown memory')
    return row

@app.delete('/api/memory/{memory_id}')
def memory_archive(memory_id:int):
    row=memory.archive(memory_id)
    if not row: raise HTTPException(404,'Unknown memory')
    return row

@app.post('/api/memory/semantic/index')
def semantic_memory_index(limit:int=1000):
    try: return semantic.index_memories(max(1,min(limit,5000)))
    except Exception as exc: raise HTTPException(400,str(exc))

@app.get('/api/memory/semantic/search')
def semantic_memory_search(q:str,limit:int=12):
    try: return semantic.search(q,max(1,min(limit,50)))
    except Exception as exc: raise HTTPException(400,str(exc))

@app.get('/api/audio/providers')
def audio_providers(): return audio.providers()

@app.post('/api/audio/transcribe-upload')
async def audio_transcribe_upload(file:UploadFile=File(...), provider:str|None=None, language:str|None=None, prompt:str=''):
    try:
        data=await file.read(25*1024*1024+1)
        if len(data)>25*1024*1024: raise ValueError('Audio upload exceeds 25 MB')
        saved=attachments.save(file.filename or 'recording.webm',data,file.content_type or 'audio/webm')
        return audio.transcribe(saved['path'],provider,language,prompt,{})
    except Exception as exc: raise HTTPException(400,str(exc))

@app.post('/api/audio/transcribe')
def audio_transcribe(path:str, provider:str|None=None, language:str|None=None, prompt:str='', options:dict|None=None):
    try: return audio.transcribe(path,provider,language,prompt,options or {})
    except Exception as exc: raise HTTPException(400,str(exc))

@app.post('/api/audio/speech')
def audio_speech(text:str, request:Request, provider:str|None=None, voice:str|None=None, response_format:str='mp3', options:dict|None=None):
    _require_admin_mode(request)
    try: return audio.synthesize(text,provider,voice,response_format,options or {})
    except Exception as exc: raise HTTPException(400,str(exc))


@app.get('/api/perception/recent')
def perception_recent(limit:int=50): return perception.recent(limit)

@app.get('/api/computer-use/sessions')
def computer_sessions(request:Request, limit:int=50):
    _require(request,'delegate'); return computer_use.recent_sessions(limit)

@app.get('/api/world/entities/{name}/neighborhood')
def world_neighborhood(name:str, depth:int=2, limit:int=100): return world_model.neighborhood(name,depth,limit)

@app.get('/api/world/facts')
def world_facts(entity:str|None=None, limit:int=100): return world_model.facts(entity,limit)

@app.post('/api/world/entities')
def world_entity(payload:dict):
    return {'id':world_model.upsert_entity(payload.get('name',''),payload.get('type','concept'),payload.get('attributes') or {})}

@app.post('/api/world/relations')
def world_relation(payload:dict):
    return {'id':world_model.relate(payload['src'],payload['relation'],payload['dst'],payload.get('attributes') or {},payload.get('confidence',1.0),payload.get('source'))}

@app.post('/api/computer-use/sessions')
def computer_start(request:Request, payload:dict=None):
    _require(request,'delegate')
    payload=payload or {}
    try:
        sid=computer_use.start(payload.get('url','about:blank'),payload.get('viewport'))
        obs=computer_use.observe(sid,0); perception.add('browser','playwright',obs.__dict__,sid)
        return {'session_id':sid,'observation':obs.__dict__}
    except Exception as exc: raise HTTPException(400,str(exc))

@app.get('/api/computer-use/sessions/{session_id}/observe')
def computer_observe(request:Request, session_id:str):
    _require(request,'delegate')
    try:
        obs=computer_use.observe(session_id,0); perception.add('browser','playwright',obs.__dict__,session_id); return obs.__dict__
    except Exception as exc: raise HTTPException(400,str(exc))

@app.post('/api/computer-use/sessions/{session_id}/action')
def computer_action(request:Request, session_id:str, payload:dict):
    _require(request,'delegate')
    try:
        result=computer_use.act(session_id,payload,require_approval=bool(payload.get('require_approval',settings.computer_use_require_approval)),approved=bool(payload.get('approved',False)))
        perception.add('browser_action','playwright',result,session_id)
        return result
    except Exception as exc: raise HTTPException(400,str(exc))

@app.post('/api/computer-use/sessions/{session_id}/next')
def computer_next(request:Request, session_id:str, goal:str):
    _require(request,'delegate')
    try:
        obs=computer_use.observe(session_id,0); perception.add('browser','playwright',obs.__dict__,session_id)
        action=computer_planner.choose_action(obs, goal); ok,reason=computer_use.policy.validate(action)
        return {'status':'proposed' if ok else 'blocked','action':action,'reason':reason,'observation':obs.__dict__}
    except Exception as exc: raise HTTPException(400,str(exc))

@app.post('/api/computer-use/sessions/{session_id}/execute-next')
def computer_execute_next(request:Request, session_id:str, goal:str, approved:bool=False):
    _require(request,'delegate')
    if settings.computer_use_require_approval and not approved: return {'status':'approval_required','reason':'Computer-use actions must be explicitly approved for execution by this endpoint.'}
    try:
        obs=computer_use.observe(session_id,0); action=computer_planner.choose_action(obs, goal); result=computer_use.act(session_id,action)
        perception.add('computer_use_step','catalyst',{'goal':goal,'action':action,'result':result},session_id)
        return result
    except Exception as exc: raise HTTPException(400,str(exc))

@app.delete('/api/computer-use/sessions/{session_id}')
def computer_close(request:Request, session_id:str):
    _require(request,'delegate'); computer_use.close(session_id); return {'ok':True,'session_id':session_id}

@app.get('/api/evals/long-horizon')
def long_horizon_recent(limit:int=20): return long_horizon.recent(limit)

@app.post('/api/evals/long-horizon')
def long_horizon_run(payload:dict):
    scenario=payload.get('scenario') or {}
    def execute(step,seq,previous):
        action=step.get('action','echo')
        if action=='runtime': return {'version':__version__,'model_configured':bool(gateway.active_profile and gateway.active_profile.configured)}
        if action=='mission_plan': return catalyst.plan_mission(step.get('objective','general objective'))
        if action=='chat': return catalyst.respond(step.get('prompt','')).__dict__
        return step.get('value',{'seq':seq,'previous_count':len(previous)})
    return long_horizon.run(scenario,execute,stop_on_failure=bool(payload.get('stop_on_failure',True)),max_steps=int(payload.get('max_steps',24)))

@app.get('/api/project/search')
def project_search(q:str,limit:int=12):
    return analysis.search(q, max(1,min(limit,50)))

@app.get('/api/project/summary')
def project_summary():
    files=0; bytes_total=0
    for x in workspace.root.rglob('*'):
        if x.is_file():
            files+=1
            try:bytes_total+=x.stat().st_size
            except OSError:pass
    return {'root':str(workspace.root),'files':files,'bytes':bytes_total,'indexed_chunks':len(analysis.search('',50))}

@app.get('/api/project/index')
def project_index():
    return analysis.index_project()

@app.get('/api/persona')
def persona_profile(request:Request):
    profile=persona.to_dict()
    profile['admin_mode']=bool(getattr(request.state,'admin',False))
    profile['enhanced_available']=bool(getattr(settings,'enhanced_admin_only',True))
    profile['mode']='enhanced' if profile['admin_mode'] else 'basic'
    return profile

@app.get('/api/audio/realtime/providers')
def realtime_providers():
    return {'providers':realtime_bridge.profiles()}

@app.get('/api/audio/realtime/health')
def realtime_health(provider:str|None=None):
    return realtime_bridge.health(provider)

@app.post('/api/audio/realtime/session')
def realtime_session_create(request:Request, session_id:str|None=None, codec:str='audio/webm', sample_rate:int=16000):
    _require(request,'voice')
    return realtime_voice.create(session_id=session_id,codec=codec,sample_rate=sample_rate)

@app.get('/api/audio/realtime/session/{session_id}')
def realtime_session_get(request:Request, session_id:str):
    _require(request,'voice')
    row=realtime_voice.get(session_id)
    if not row: raise HTTPException(404,'Unknown realtime audio session')
    return row

@app.post('/api/audio/realtime/session/{session_id}/finalize')
def realtime_session_finalize(request:Request, session_id:str, provider:str|None=None, language:str|None=None):
    _require(request,'voice')
    row=realtime_voice.get(session_id)
    if not row: raise HTTPException(404,'Unknown realtime audio session')
    realtime_voice.close(session_id,'finalized')
    result=audio.transcribe(realtime_voice.audio_path(session_id),provider=provider,language=language)
    return {'session':realtime_voice.get(session_id),'transcription':result}

@app.websocket('/api/audio/realtime/ws/{session_id}')
async def realtime_audio_ws(websocket:WebSocket, session_id:str):
    supplied=websocket.cookies.get('catalyst_session','') or websocket.headers.get('authorization','').removeprefix('Bearer ').strip() or websocket.headers.get('x-catalyst-token','')
    enabled=bool(getattr(settings,'api_token','') or getattr(settings,'api_tokens',{}))
    if enabled:
        auth=identity.authenticate(supplied, websocket.headers.get(getattr(settings,'auth_subject_header','x-catalyst-subject'),'creator'))
        admin=identity.require_admin(supplied)
        if not auth.authenticated and not admin:
            await websocket.close(code=4401); return
        if not policy.allowed(Principal(subject='creator' if admin else auth.principal.subject, role='creator' if admin else auth.principal.role),'voice'):
            await websocket.close(code=4403); return
    await websocket.accept()
    try:
        if not realtime_voice.get(session_id):
            await websocket.send_json({'status':'error','error':'Unknown realtime session'}); await websocket.close(code=4404); return
        avatar_controller.set('listening', emotion='neutral', action='listen', hint='Live Talk is listening.', source='voice')
        await websocket.send_json({'status':'connected','session':realtime_voice.get(session_id)})
        while True:
            message=await websocket.receive()
            if message.get('bytes') is not None:
                row=realtime_voice.append(session_id,message['bytes']); await websocket.send_json({'status':'chunk','session':row})
            elif message.get('text') is not None:
                payload=json.loads(message['text'])
                action=payload.get('action')
                if action=='close':
                    avatar_controller.set('idle', emotion='neutral', action='idle', hint='Live Talk ended.', source='voice')
                    await websocket.send_json({'status':'closed','session':realtime_voice.close(session_id,'closed')}); await websocket.close(); return
                if action=='stats': await websocket.send_json({'status':'stats','session':realtime_voice.get(session_id)}); continue
                await websocket.send_json({'status':'ignored','reason':'Unknown realtime message action'})
    except WebSocketDisconnect:
        try: realtime_voice.close(session_id,'disconnected')
        except Exception: pass

@app.post('/api/research/evidence')
def research_evidence(request:Request, query:str, limit:int=6):
    _require(request,'research')
    return evidence_research.research(query,max(1,min(limit,12)))

@app.get('/api/research/evidence')
def research_evidence_artifacts():
    root=Path('catalyst_data/evidence'); root.mkdir(parents=True,exist_ok=True)
    out=[]
    for p in sorted(root.glob('evidence-*.json'),reverse=True)[:50]:
        try: out.append(json.loads(p.read_text(encoding='utf-8')))
        except Exception: pass
    return out

@app.post('/api/improvement/experiments')
def improvement_create(request:Request, title:str, patch:str='', test_command:str='python -m pytest -q', reason:str='', baseline_command:str='python -m pytest -q'):
    _require(request,'improvement')
    return improvement_lab.create(title,patch,test_command,reason,baseline_command)

@app.post('/api/improvement/experiments/{experiment_id}/run')
def improvement_run(request:Request, experiment_id:str, timeout:int=1200):
    _require(request,'improvement')
    return improvement_lab.run(experiment_id,max(30,min(int(timeout),3600)))

@app.get('/api/improvement/experiments')
def improvement_list():
    return improvement_lab.recent(100)

@app.post('/api/improvement/experiments/{experiment_id}/promote')
def improvement_promote(request:Request, experiment_id:str, confirmed:bool=False):
    _require(request,'admin')
    if not confirmed: return {'status':'approval_required','reason':'Promotion changes production source; pass confirmed=true after explicit creator approval.'}
    return improvement_lab.promote(experiment_id)

@app.post('/api/improvement/experiments/{experiment_id}/rollback')
def improvement_rollback(request:Request, experiment_id:str, confirmed:bool=False):
    _require(request,'admin')
    if not confirmed: return {'status':'approval_required','reason':'Rollback changes production source; pass confirmed=true after explicit creator approval.'}
    return improvement_lab.rollback(experiment_id)

@app.get('/api/health')
def health_status():
    p=gateway.active_profile
    health.set('active_model','ok' if p and p.configured else 'degraded','configured model' if p and p.configured else 'No active model configured')
    health.set('job_worker','ok' if job_worker.thread and job_worker.thread.is_alive() else 'degraded')
    health.set('workspace','ok',str(workspace.root))
    return health.report()

@app.get('/api/approvals')
def approval_list(status:str|None=None): return approvals.list(status)

@app.post('/api/approvals/{approval_id}/resolve')
def approval_resolve(request:Request, approval_id:str, approved:bool, reason:str=''):
    _require(request,'approval')
    row=approvals.get(approval_id)
    if not row: raise HTTPException(404,'Unknown approval')
    if row['status']!='pending': return row
    tool=tools.get(row['tool']); args=json.loads(row['arguments'])
    if approved and not tool: raise HTTPException(400,'Tool is no longer available')
    result=None
    if approved:
        try: result={'status':'ok','result':tool.handler(**args)}
        except Exception as e: result={'status':'error','error':str(e)}
    resolved=approvals.resolve(approval_id,approved,result,reason)
    if approved and resolved and resolved.get('status')=='approved':
        resumed=catalyst.resume_approval(resolved)
        resolved['resume']={'answer':resumed.answer,'steps':resumed.steps,'tools':resumed.tools_used,'verified':resumed.verified,'stopped_reason':resumed.stopped_reason}
    return resolved

@app.get('/api/missions')
def missions_list(status:str|None=None): return missions.list(status)

@app.post('/api/missions')
def missions_create(objective:str):
    mid=missions.create(objective); missions.update(mid,'queued',plan={'objective':objective,'recommended_agent':agents.choose(objective)})
    jid=jobs.create('mission',{'objective':objective,'mission_id':mid},max_attempts=3)
    return {'mission_id':mid,'job_id':jid}

@app.get('/api/missions/{mission_id}')
def mission_get(mission_id:str):
    row=missions.get(mission_id)
    if not row: raise HTTPException(404,'Unknown mission')
    return row


@app.get('/api/observability')
def observability_report(): return {'summary':observability.summary(),'recent':observability.recent(100)}
@app.get('/api/metrics')
def metrics():
    if not settings.metrics_enabled: raise HTTPException(404,'Metrics disabled')
    return observability.counters()
@app.get('/api/missions/{mission_id}/steps')
def mission_steps(mission_id:str):
    if not missions.get(mission_id): raise HTTPException(404,'Unknown mission')
    return missions.steps(mission_id)
@app.post('/api/missions/{mission_id}/pause')
def mission_pause(request:Request, mission_id:str):
    _require(request,'automation')
    row=missions.get(mission_id)
    if not row: raise HTTPException(404,'Unknown mission')
    if row['status'] in {'completed','failed','cancelled'}: return row
    return missions.pause(mission_id)

@app.post('/api/missions/{mission_id}/cancel')
def mission_cancel(request:Request, mission_id:str, reason:str='cancelled by creator'):
    _require(request,'automation')
    row=missions.get(mission_id)
    if not row: raise HTTPException(404,'Unknown mission')
    return missions.cancel(mission_id,reason)

@app.post('/api/missions/{mission_id}/resume')
def mission_resume(request:Request, mission_id:str):
    _require(request,'automation')
    row=missions.get(mission_id)
    if not row: raise HTTPException(404,'Unknown mission')
    jid=jobs.create('mission',{'objective':row['objective'],'mission_id':mission_id},max_attempts=3)
    missions.update(mission_id,'queued',checkpoint={'phase':'resumed'})
    return {'ok':True,'job_id':jid}
@app.get('/api/improvement/proposals')
def improvement_proposals():
    p=Path('proposals'); p.mkdir(exist_ok=True); return [json.loads(x.read_text()) for x in sorted(p.glob('*.json'),reverse=True)[:100]]
@app.post('/api/improvement/propose')
def improvement_propose(change:str,reason:str='',test_plan:str=''): return {'path':improvements.propose(change,reason,test_plan)}


@app.get('/api/security/policy')
def security_policy(): return policy.describe()
@app.get('/api/runtime/plan')
def runtime_plan(objective:str): return catalyst.plan_mission(objective)
@app.post('/api/evals/run')
def evals_run(payload:dict):
    tests=payload.get('tests') or [{'id':'status','expect':'runtime'}]
    def runner(t):
        if t.get('expect')=='runtime': return {'version':__version__,'model_configured':bool(gateway.active_profile and gateway.active_profile.configured)}
        if t.get('expect')=='mission_plan': return catalyst.plan_mission(t.get('objective','general objective'))
        return {'echo':t}
    return evals.run(tests,runner)

@app.get('/api/models/catalog')
def model_catalog():
    return {
        'primary': [
            {'name':'GPT-5.6 Sol','model':'gpt-5.6-sol','role':'general','description':'Primary Catalyst reasoning model profile.'},
            {'name':'GPT-5.6 Luna','model':'gpt-5.6-luna','role':'general','description':'Primary Catalyst reasoning/personality model profile.'},
        ],
        'alternatives': [
            {'name':'Qwen 2.5 72B','model':'qwen2.5-72b','role':'general','description':'Large open-model profile.'},
            {'name':'Qwen 2.5 14B','model':'qwen2.5-14b','role':'general','description':'Smaller/faster open-model profile.'},
            {'name':'DeepSeek-V3','model':'deepseek-v3','role':'general','description':'General reasoning/coding profile.'},
            {'name':'DeepSeek-Coder','model':'deepseek-coder','role':'coding','description':'Coding-focused profile.'},
            {'name':'Mistral Large 2','model':'mistral-large-2','role':'general','description':'General-purpose large-model profile.'},
        ]
    }

@app.get('/api/providers')
def providers(): return gateway.list_profiles()
@app.post('/api/providers')
def save_provider(request:Request, req:ProfileRequest):
    _require(request,'model'); gateway.upsert_profile(ProviderProfile(req.name,req.base_url,req.model,req.api_key,req.kind,tuple(req.capabilities),req.role,req.options)); return {'ok':True,'providers':gateway.list_profiles()}
@app.delete('/api/providers/{name}')
def provider_delete(request:Request, name:str):
    _require(request,'model')
    if name not in gateway.profiles: raise HTTPException(404,'Unknown provider')
    if name==gateway.active_name: raise HTTPException(400,'Cannot delete the active provider; activate another profile first')
    gateway.profiles.pop(name,None);
    p=Path(settings.secrets_path)
    try:
        raw=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'profiles':{}}
        raw.setdefault('profiles',{}).pop(name,None); p.write_text(json.dumps(raw,indent=2),encoding='utf-8')
    except Exception as exc: raise HTTPException(500,str(exc))
    gateway._refresh_all(); return {'ok':True,'name':name}

@app.post('/api/providers/{name}/activate')
def activate(request:Request, name):
    _require(request,'model')
    try: gateway.activate(name)
    except KeyError: raise HTTPException(404,'Unknown profile')
    return {'ok':True,'active':name}
@app.get('/api/providers/health')
def provider_health(): return gateway.health()
@app.get('/api/integrations')
def integrations_list():
    return integrations.describe()

@app.get('/api/devices')
def list_devices(request:Request):
    _require(request,'device')
    return devices.list()

@app.post('/api/devices/register')
def register_device(req:DeviceRegisterRequest):
    did=devices.register(req.name,req.platform,req.version,req.capabilities,req.metadata,req.device_id)
    row=devices.get(did)
    if not req.device_id:
        row['device_token']=devices.issue_token(did)
    else:
        row['device_token']=None
    return row

def _require_device_auth(request: Request, device_id: str):
    if bool(getattr(request.state, 'admin', False)):
        return
    token=request.headers.get('x-catalyst-device-token','')
    if not devices.authenticate(device_id, token):
        raise HTTPException(status_code=401, detail='Device authentication required')

@app.post('/api/devices/{device_id}/heartbeat')
def device_heartbeat(device_id:str,req:DeviceHeartbeatRequest,request:Request):
    _require_device_auth(request,device_id)
    row=devices.heartbeat(device_id,req.metadata)
    if not row: raise HTTPException(404,'Unknown device')
    return row

@app.post('/api/devices/{device_id}/command')
def device_command(request:Request,device_id:str,action:str,payload:dict|None=None,requires_confirmation:bool=True):
    _require(request,'automation')
    if requires_confirmation and not getattr(request.state,'admin',False):
        raise HTTPException(403,'Creator approval required for device command')
    return shell_bridge.command(device_id,action,payload,requires_confirmation)

@app.get('/api/devices/{device_id}/commands')
def device_commands(request:Request,device_id:str,status:str|None=None,limit:int=100):
    _require_device_auth(request,device_id)
    if not devices.get(device_id): raise HTTPException(404,'Unknown device')
    return device_control.list(device_id,status,limit)

@app.post('/api/devices/{device_id}/commands')
def issue_device_command(request:Request,device_id:str,action:str,payload:dict|None=None,requires_confirmation:bool=True,ttl_seconds:int=300):
    _require(request,'automation')
    if requires_confirmation and not getattr(request.state,'admin',False):
        raise HTTPException(403,'Creator approval required for device command')
    try:return device_control.issue(device_id,action,payload,requires_confirmation,ttl_seconds)
    except ValueError as exc:raise HTTPException(400,str(exc))

@app.post('/api/devices/{device_id}/commands/claim')
def claim_device_command(device_id:str,request:Request):
    _require_device_auth(request,device_id)
    try:return device_control.claim(device_id) or {'status':'empty'}
    except ValueError as exc:raise HTTPException(404,str(exc))

@app.post('/api/device-commands/{command_id}/complete')
def complete_device_command(command_id:str,result:dict|None=None,request:Request=None):
    if request is None: raise HTTPException(401,'Device authentication required')
    device_id=device_control.device_id_for_command(command_id)
    if not device_id: raise HTTPException(404,'Unknown command')
    _require_device_auth(request,device_id)
    row=device_control.complete(command_id,result)
    if not row: raise HTTPException(404,'Unknown command')
    return row

@app.post('/api/device-commands/{command_id}/fail')
def fail_device_command(command_id:str,error:str,request:Request=None):
    if request is None: raise HTTPException(401,'Device authentication required')
    device_id=device_control.device_id_for_command(command_id)
    if not device_id: raise HTTPException(404,'Unknown command')
    _require_device_auth(request,device_id)
    row=device_control.fail(command_id,error)
    if not row: raise HTTPException(404,'Unknown command')
    return row

@app.get('/api/reasoning/recent')
def reasoning_recent(limit:int=20):
    return {'protocol':'catalyst.reasoning.v3','runs':monster.reasoning.memory.recent(limit)}

@app.post('/api/reasoning/analyze')
def reasoning_analyze(req:ReasoningRequest, request:Request):
    _require_admin_mode(request)
    trace=monster.reasoning.start(req.objective, context={'evidence_available':True})
    plan=monster.reasoning.build_plan(trace)
    if req.use_model:
        plan=monster.reasoning.refine_plan(trace,plan)
    return {'protocol':'catalyst.reasoning.v3','trace':trace.as_dict(),'plan':plan}

@app.post('/api/apex/plan')
def apex_plan(req:ReasoningRequest, request:Request):
    _require_admin_mode(request)
    return monster.apex_plan(req.objective)
@app.get('/api/apex/missions')
def apex_missions(state:str|None=None,limit:int=50):
    return monster.apex.store.list(state,limit)

@app.get('/api/apex/missions/{mission_id}')
def apex_mission_get(mission_id:str):
    row=monster.apex.store.get(mission_id)
    if not row: raise HTTPException(404,'Unknown Apex mission')
    row['events']=monster.apex.store.events(mission_id,100)
    return row

@app.post('/api/apex/missions/{mission_id}/state')
def apex_mission_state(request:Request,mission_id:str,state:str,checkpoint:int|None=None,detail:str='state transition'):
    _require(request,'automation')
    try:return monster.apex.transition(mission_id,state,checkpoint=checkpoint,detail=detail)
    except KeyError:raise HTTPException(404,'Unknown Apex mission')
    except ValueError as exc:raise HTTPException(400,str(exc))

@app.post('/api/apex/missions/{mission_id}/dispatch')
def apex_mission_dispatch(request:Request, mission_id:str, execute:bool=False, approval:bool=False):
    if execute:
        _require(request,'automation')
        if not getattr(request.state,'admin',False):
            raise HTTPException(403,'Creator approval is required for Apex execution.')
        approval=True
    try:
        return monster.apex.dispatch(mission_id,execute=execute,approval=approval)
    except KeyError:
        raise HTTPException(404,'Unknown Apex mission')

@app.post('/api/reasoning/brief')
def reasoning_brief(req:ReasoningRequest, request:Request):
    _require_admin_mode(request)
    plan=monster.reasoning.choose(req.objective,context={'evidence_available':True})
    brief=monster.deliberator.analyze(req.objective,plan=plan,context={'evidence_available':True})
    return {'protocol':'catalyst.reasoning.brief.v1','brief':brief.as_dict(),'plan':plan.as_dict()}


@app.get('/api/monster/status')
def monster_status(): return monster.status()

@app.post('/api/monster/mission')
def monster_mission(req:MonsterMissionRequest, request:Request):
    if req.execute and not bool(getattr(request.state,'admin',False)):
        raise HTTPException(403,'Creator approval is required for monster execution.')
    return monster.mission(req.objective, execute=req.execute, approval=req.approval)

@app.post('/api/monster/production-mission')
def monster_production_mission(req:MonsterMissionRequest, request:Request):
    if req.execute and not bool(getattr(request.state,'admin',False)):
        raise HTTPException(403,'Creator approval is required for monster execution.')
    return monster.production_mission(req.objective, execute=req.execute, approval=req.approval)

@app.get('/api/engineering/repo-map')
def engineering_repo_map(): return monster.engineering.codebase.repo_map()

@app.post('/api/engineering/plan')
def engineering_plan(req:MonsterMissionRequest):
    run=monster.engineering.plan(req.objective)
    return {'protocol':monster.engineering.protocol,'objective':run.objective,'status':run.status,'plan':run.plan,'evidence':run.evidence}

@app.get('/api/engineering/tools')
def engineering_tools():
    return {'protocol':monster.engineering.protocol,'tools':monster.engineering.toolbox.schemas()}

@app.post('/api/engineering/run')
def engineering_run(req:MonsterMissionRequest, request:Request):
    if req.execute and not bool(getattr(request.state,'admin',False)):
        raise HTTPException(403,'Creator approval is required for engineering execution.')
    run=monster.engineering.run(req.objective, execute=req.execute, approval=req.approval and bool(getattr(request.state,'admin',False)))
    return run.as_dict()

@app.get('/api/engineering/runs/{run_id}')
def engineering_run_get(run_id:str):
    row=monster.engineering.state.get(run_id)
    if not row: raise HTTPException(404,'Unknown engineering run')
    return row

@app.get('/api/situational/context')
def situational_context(): return situational.context()

@app.post('/api/situational/scan')
def situational_scan(request:Request):
    _require(request,'automation'); return situational.scan()

@app.post('/api/situational/signals')
def situational_signal(kind:str,source:str,title:str,detail:str,severity:float=.5,actionable:bool=True,metadata:dict|None=None):
    return situational.ingest(kind,source,title,detail,severity,metadata,actionable)

@app.get('/api/situational/suggestions')
def situational_suggestions(status:str='pending',limit:int=20):
    return situational.store.list_suggestions(status,limit)

@app.post('/api/situational/suggestions/{suggestion_id}/resolve')
def situational_resolve(request:Request,suggestion_id:str,status:str):
    _require(request,'automation');
    try:return situational.act_on_suggestion(suggestion_id,status)
    except ValueError as exc:raise HTTPException(400,str(exc))

@app.get('/api/cognition/fusion')
def cognition_fusion():
    return unified.capability_fusion()

@app.get('/api/cognition/snapshot')
def cognition_snapshot(q: str = ''):
    return unified.snapshot(q)

@app.post('/api/cognition/deliberate')
def cognition_deliberate(objective: str, candidates: list[str] | None = None):
    return unified.deliberate(objective, candidates=candidates)

@app.post('/api/cognition/event')
def cognition_event(kind: str, source: str, payload: dict):
    return events.emit(kind, source, payload)

@app.post('/api/cognition/plan')
def cognition_plan(objective: str, max_steps: int = 12):
    return deliberator.propose(objective, unified.snapshot(objective), max_steps)

@app.post('/api/voice/transcribe-cognitive')
def voice_transcribe_cognitive(audio_path: str, request:Request, session_id: str | None = None, provider: str | None = None, language: str | None = None):
    _require_admin_mode(request)
    try: return voice_turns.transcribe_and_remember(audio_path,session_id,provider,language)
    except Exception as exc: raise HTTPException(400,str(exc))

@app.post('/api/voice/speak')
def voice_speak(text: str, provider: str | None = None, voice: str | None = None):
    try:
        avatar_controller.set('speaking', emotion='warm', action='speak', hint='Voice output is playing.', source='voice')
        return voice_turns.speak(text,provider,voice)
    except Exception as exc: raise HTTPException(400,str(exc))

@app.get('/api/events')
def events_recent(limit: int = 100, kind: str | None = None):
    return events.recent(limit, kind)

@app.post('/api/perception/observe')
def perception_observe(source: str, modality: str, content: dict, confidence: float = .7, session_id: str | None = None):
    return observations.ingest(source=source, modality=modality, content=content, confidence=confidence, session_id=session_id)

@app.post('/api/perception/screen')
def perception_screen(source: str, image_path: str | None = None, text: str = '', app: str = '', url: str = '', confidence: float = .8, session_id: str | None = None):
    return observations.screen(source, image_path, text, app, url, confidence, session_id)

@app.get('/api/device-agent/capabilities')
def device_agent_capabilities():
    return {'protocol':'catalyst.device-agent.v1','platform':__import__('platform').system(),'capabilities':host_executor.capabilities()}

@app.post('/api/device-agent/execute')
def device_agent_execute(request: Request, action: str, payload: dict | None = None):
    if action not in {'capture_screen','get_system_info','get_clipboard'} and not getattr(request.state,'admin',False):
        raise HTTPException(403,'Creator approval is required for consequential host-device execution')
    _require(request,'device')
    try:
        result=host_executor.execute(action,payload)
        events.emit('device.local_execution','host-agent',{'action':action,'result':result})
        return result
    except PermissionError as exc: raise HTTPException(403,str(exc))
    except Exception as exc: raise HTTPException(400,str(exc))

@app.post('/api/device-agent/heartbeat-cycle')
def device_agent_heartbeat_cycle(request: Request, device_id: str, metadata: dict | None = None):
    _require_device_auth(request,device_id)
    row=devices.heartbeat(device_id, metadata or {})
    if not row: raise HTTPException(404,'Unknown device')
    return {'device':row,'status':'heartbeat_recorded'}

@app.get('/api/engineering/status')
def engineering_status():
    return engineering.status()

@app.get('/api/engineering/catalog')
def engineering_catalog():
    return EngineeringCatalog.list_sources()

@app.get('/api/engineering/recommend')
def engineering_recommend(objective: str):
    return engineering.recommend(objective)

@app.get('/api/engineering/workflow')
def engineering_workflow(objective: str):
    return engineering_planner.plan(objective)

@app.get('/api/engineering/geometry/inspect')
def engineering_geometry_inspect(path: str):
    try:
        return engineering.inspect_geometry(path)
    except FileNotFoundError:
        raise HTTPException(404, 'Engineering geometry file not found')
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

@app.get('/api/integrations/health')
def integrations_health():

    return integrations.health()

@app.post('/api/integrations/tc/submit')
def integrations_tc_submit(prompt:str, wait:bool=True):
    return integrations.tc.submit(prompt, wait=wait).as_dict()

@app.post('/api/integrations/tc/{task_id}/approve')
def integrations_tc_approve(request:Request, task_id:str, nonce:str, decided_by:str='Catalyst'):
    _require(request,'approval')
    return integrations.tc.approve(task_id, nonce, decided_by).as_dict()

@app.post('/api/integrations/tc/{task_id}/reject')
def integrations_tc_reject(request:Request, task_id:str, nonce:str, decided_by:str='Catalyst'):
    _require(request,'approval')
    return integrations.tc.reject(task_id, nonce, decided_by).as_dict()

@app.get('/api/plugins')
def list_plugins(): return plugins.list()
@app.post('/api/plugins/{name}/enable')
def enable_plugin(request:Request, name):
    _require(request,'admin')
    try: plugins.enable(name)
    except KeyError: raise HTTPException(404,'Unknown plugin')
    return {'ok':True,'plugins':plugins.list()}
@app.post('/api/plugins/{name}/disable')
def disable_plugin(request:Request, name):
    _require(request,'admin'); plugins.disable(name); return {'ok':True,'plugins':plugins.list()}
@app.get('/api/sessions')
def list_sessions(q:str|None=None,limit:int=50): return sessions.search(q, max(1,min(limit,100))) if q else sessions.list(max(1,min(limit,100)))
@app.post('/api/sessions')
def new_session(): return {'session_id':sessions.create('New conversation')}
@app.post('/api/sessions/{session_id}/cancel')
def cancel_session(session_id): sessions.cancel(session_id); return {'ok':True}
@app.post('/api/sessions/{session_id}/rename')
def rename_session(session_id:str,title:str):
    if not sessions.read(session_id,1) and not any(x['id']==session_id for x in sessions.list(500)): raise HTTPException(404,'Unknown session')
    sessions.rename(session_id,title); return {'ok':True,'session_id':session_id,'title':title[:120]}
@app.delete('/api/sessions/{session_id}')
def delete_session(session_id:str):
    if not any(x['id']==session_id for x in sessions.list(500)): raise HTTPException(404,'Unknown session')
    sessions.delete(session_id); return {'ok':True}
@app.get('/api/sessions/{session_id}')
def get_session(session_id):
    rows=sessions.read(session_id,500)
    listed={x['id']:x for x in sessions.list(500)}
    meta=listed.get(session_id)
    if meta is None: raise HTTPException(404,'Unknown session')
    return {'id':session_id,'title':meta.get('title','Conversation'),'created':meta.get('created'),'updated':meta.get('updated'),'cancelled':bool(meta.get('cancelled')),'summary':sessions.get_summary(session_id),'messages':rows}
@app.post('/api/sessions/{session_id}/compact')
def compact_session(session_id):
    from ..context import ContextManager
    try: return {'ok':True,'summary':ContextManager(sessions,memory,gateway,settings.context_keep_messages,settings.context_compact_trigger).compact(session_id,sessions.read(session_id,1000))}
    except Exception as e: raise HTTPException(400,str(e))
@app.post('/api/chat')
def chat(req:ChatRequest, request:Request):
    _require_admin_mode(request)
    sid=sessions.ensure(req.session_id)
    try:
        avatar_controller.set('thinking', emotion='focused', action='think', hint='Thinking through your request.', source='cognition')
        result=catalyst.respond(req.message,session_id=sid,attachments=req.attachments,access_mode='admin' if getattr(request.state,'admin',False) else 'normal')
        avatar_controller.set('success', emotion='warm', action='celebrate', hint='Response complete.', source='cognition', appearance=avatar_controller.get().get('appearance'))
        return {'session_id':sid,'answer':result.answer,'steps':result.steps,'tools':result.tools_used,'verified':result.verified,'stopped_reason':result.stopped_reason}
    except Exception as e:
        avatar_controller.set('error', emotion='concerned', action='concern', hint='Something needs attention.', source='cognition')
        plan=_self_heal_plan(str(e))
        return {'session_id':sid,'answer':f"I hit a runtime error: {e}\n\nSelf-heal suggestion: {plan['category']}. Open Self-Heal for steps.", 'steps':[], 'tools':[], 'verified':False, 'stopped_reason':'error', 'self_heal':plan}
@app.post('/api/chat/stream')
def chat_stream(req:ChatRequest, request:Request):
    sid=sessions.ensure(req.session_id)
    def events():
        avatar_controller.set('thinking', emotion='focused', action='think', hint='Thinking through your request.', source='cognition')
        try:
            for event in catalyst.stream_response(req.message,session_id=sid,attachments=req.attachments,access_mode='admin' if getattr(request.state,'admin',False) else 'normal'):
                event_type=event.get('type') if isinstance(event,dict) else ''
                if event_type in {'step','tool_calls','tool_result'}:
                    avatar_controller.set('thinking', emotion='focused', action='think', hint='Working with Catalyst tools.', source='cognition')
                elif event_type in {'content'}:
                    avatar_controller.set('speaking', emotion='warm', action='speak', hint='Composing a response.', source='cognition')
                elif event_type in {'done','answer','final'}:
                    avatar_controller.set('success', emotion='warm', action='celebrate', hint='Response complete.', source='cognition')
                yield f'data: {json.dumps(event,ensure_ascii=False)}\n\n'
        except Exception as e:
            avatar_controller.set('error', emotion='concerned', action='concern', hint='Something needs attention.', source='cognition')
            plan=_self_heal_plan(str(e))
            yield f'data: {json.dumps({"type":"error","error":str(e),"self_heal":plan},ensure_ascii=False)}\n\n'
    return StreamingResponse(events(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.post('/api/self-heal/suggest')
def self_heal_suggest(req:dict):
    """Return a self-heal plan for an error string."""
    return _self_heal_plan(str(req.get('error') or ''))
@app.post('/api/index')
def index(): return analysis.index_project()
@app.get('/api/search')
def search(q:str,limit:int=12): return {'results':analysis.search(q,limit)}
@app.get('/api/inspect-data')
def inspect_data(path:str,sample_rows:int=1000):
    try:return inspector.inspect(path,sample_rows)
    except Exception as e: raise HTTPException(400,str(e))
@app.get('/api/analyze')
def analyze(path:str,max_rows:int=1000):
    try:return analysis.analyze_file(path,max_rows)
    except Exception as e: raise HTTPException(400,str(e))
@app.post('/api/analyze-many')
def analyze_many(paths:list[str],max_rows:int=2000):
    try:return workbench.analyze_many(paths,max_rows)
    except Exception as e: raise HTTPException(400,str(e))
@app.post('/api/compile-memory')
def compile_memory(project_name:str|None=None): return compiler.compile(project_name)
@app.get('/api/agents')
def list_agents(): return agents.describe()

class TeamRequest(BaseModel):
    objective:str=Field(min_length=1)
    mode:str='selector'
    members:list[dict[str,str]]=Field(default_factory=list)
    max_turns:int=8
    edges:list[dict[str,str]]=Field(default_factory=list)

@app.get('/api/teams')
def list_team_modes():
    return {'modes':sorted(TeamEngine.MODES),'patterns':['selector','round_robin','swarm_handoff','graph_flow'],'max_turns':24}

@app.post('/api/teams/run')
def run_team(req:TeamRequest):
    try:
        result=team_engine.run(req.objective,req.members,req.mode,req.max_turns,req.edges)
        return {'status':result.status,'objective':result.objective,'mode':result.mode,'turns':result.turns,'transcript':result.transcript,'final':result.final,'stopped_reason':result.stopped_reason}
    except Exception as exc:
        raise HTTPException(400,str(exc))
@app.post('/api/agents/run')
def run_agents(items:list[dict]): return {'results':agent_executor.run(items)}
@app.post('/api/integrations/swe-agent/run')
def integrations_swe_agent_run(
    repo_path:str|None=None,
    github_url:str|None=None,
    problem_path:str|None=None,
    problem_github_url:str|None=None,
    config:str|None=None,
    model:str|None=None,
    output_dir:str|None=None,
    extra_args:list[str]|None=None,
    timeout:int|None=None,
):
    result=integrations.sweagent.run(
        repo_path=repo_path, github_url=github_url,
        problem_path=problem_path, problem_github_url=problem_github_url,
        config=config, model=model, output_dir=output_dir,
        extra_args=extra_args, timeout=timeout,
    )
    return result.as_dict()

@app.get('/api/integrations/{name}')
def integration_detail(name:str):
    items={x['name']:x for x in integrations.describe()}
    if name not in items: raise HTTPException(404,'Unknown integration')
    return items[name]

@app.get('/api/tasks')
def list_tasks(status:str|None=None): return tasks.list(status)
@app.post('/api/tasks')
def create_task(req:TaskRequest): return {'task_id':tasks.create(req.title,req.description,req.agent,req.priority)}

@app.get('/api/tasks/{task_id}')
def get_task(task_id:str):
    row=tasks.get(task_id)
    if not row: raise HTTPException(404,'Unknown task')
    return row
@app.post('/api/tasks/claim')
def claim_task(): return tasks.claim() or {'status':'empty'}
@app.post('/api/execute')
def execute(command:str,cwd:str='.'):
    if not settings.allow_shell: raise HTTPException(403,'Shell execution is disabled')
    try:
        result=agent_executor.sandbox.run(command,cwd); audit.log('execution.request',details={'command':command,'cwd':cwd,'status':result.status,'mode':result.mode}); return result.__dict__
    except Exception as e: raise HTTPException(400,str(e))
@app.get('/api/audit')
def audit_log(limit:int=100): return audit.list(limit)
@app.get('/api/jobs')
def jobs_list(status:str|None=None): return jobs.list(status)
@app.post('/api/jobs')
def jobs_create(req:JobRequest): return {'job_id':jobs.create(req.kind,req.payload,req.max_attempts)}
@app.get('/api/jobs/{job_id}')
def jobs_get(job_id:str):
    row=jobs.get(job_id)
    if not row: raise HTTPException(404,'Unknown job')
    return row
@app.post('/api/jobs/{job_id}/retry')
def jobs_retry(job_id:str):
    row=jobs.get(job_id)
    if not row: raise HTTPException(404,'Unknown job')
    jobs.retry(job_id); return {'ok':True,'job_id':job_id,'status':'queued'}
@app.post('/api/jobs/{job_id}/cancel')
def jobs_cancel(job_id:str):
    row=jobs.cancel(job_id)
    if not row: raise HTTPException(404,'Unknown job')
    return row

@app.post('/api/jobs/{job_id}/checkpoint')
def jobs_checkpoint(job_id:str,payload:dict):
    if not jobs.get(job_id): raise HTTPException(404,'Unknown job')
    jobs.checkpoint(job_id,payload); return {'ok':True}
@app.get('/api/provenance')
def provenance_list(kind:str|None=None,limit:int=200): return provenance.list(kind,limit)
@app.post('/api/provenance')
def provenance_add(kind:str,source:str,claim:str,metadata:dict|None=None): return {'id':provenance.add(kind,source,claim,metadata)}
@app.get('/api/artifacts')
def artifact_dir(): return {'path':str(artifacts.root),'items':artifacts.list()}
@app.get('/api/artifacts/{name}')
def artifact_get(name:str):
    path=(artifacts.root/Path(name).name).resolve()
    if artifacts.root.resolve() not in path.parents or not path.exists(): raise HTTPException(404,'Unknown artifact')
    return FileResponse(path)

@app.delete('/api/artifacts/{name}')
def artifact_delete(name:str):
    try:return artifacts.delete(name)
    except Exception:raise HTTPException(404,'Unknown artifact')

@app.post('/api/attachments')
async def upload_attachment(file: UploadFile = File(...)):
    max_bytes=12*1024*1024
    try:
        data=bytearray()
        while True:
            chunk=await file.read(1024*1024)
            if not chunk:
                break
            data.extend(chunk)
            if len(data)>max_bytes:
                raise HTTPException(413,f'Attachment exceeds {max_bytes//(1024*1024)} MB limit')
        return attachments.save(file.filename or 'upload.bin',bytes(data),file.content_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400,str(e))

@app.get('/api/attachments/{attachment_id}')
def attachment_get(attachment_id:str):
    try:
        path=attachments.resolve(attachment_id)
        return {'id':path.name,'name':path.name,'size':path.stat().st_size}
    except Exception: raise HTTPException(404,'Unknown attachment')

@app.delete('/api/attachments/{attachment_id}')
def attachment_delete(attachment_id:str):
    try:return attachments.delete(attachment_id)
    except Exception:raise HTTPException(404,'Unknown attachment')

@app.get('/api/attachments')
def list_attachments():
    return [{'id':x.name,'name':x.name,'size':x.stat().st_size} for x in attachments.root.iterdir() if x.is_file()]


@app.get('/api/media/providers')
def media_providers():
    return media.provider_profiles()

@app.get('/api/media/edit-operations')
def media_edit_operations():
    return [
        {'name':'trim','description':'Cut a clip between start/end seconds','options':['start','end']},
        {'name':'resize','description':'Resize while preserving aspect ratio','options':['width','height']},
        {'name':'crop','description':'Crop to exact dimensions','options':['width','height','x','y']},
        {'name':'rotate','description':'Rotate 90/180/270 degrees','options':['degrees']},
        {'name':'concat','description':'Join compatible video clips','options':[]},
        {'name':'mute','description':'Remove audio','options':[]},
        {'name':'thumbnail','description':'Extract a still frame','options':['at']},
        {'name':'extract_audio','description':'Extract MP3 audio','options':[]},
        {'name':'add_audio','description':'Replace video audio with an audio input','options':[]},
        {'name':'mix_audio','description':'Mix original and supplied audio','options':[]},
        {'name':'speed','description':'Change playback speed','options':['factor']},
        {'name':'normalize_audio','description':'Normalize audio loudness','options':[]},
        {'name':'reverse','description':'Reverse audio/video','options':[]},
    ]

@app.get('/api/media/catalog')
def media_catalog():
    return [x for x in artifacts.list() if x.get('media_kind') or x.get('type','').startswith(('image/','video/','audio/'))]

@app.post('/api/media/plan')
def media_plan(req:dict):
    concept=str(req.get('concept','')).strip()
    if not concept: raise HTTPException(400,'concept is required')
    try:
        return creative_planner.plan(concept,req.get('mode','video'),req.get('style',''),int(req.get('shot_limit',8)))
    except Exception as e:
        raise HTTPException(400,str(e))

@app.post('/api/engineering/mission-plan')
def engineering_mission_plan(req:dict):
    objective=str(req.get('objective','')).strip()
    if not objective: raise HTTPException(400,'objective is required')
    try: return engineering_missions.prepare(objective,req.get('focus_files') or []).as_dict()
    except Exception as e: raise HTTPException(400,str(e))

@app.post('/api/media/production-plan')
def media_production_plan(req:dict):
    concept=str(req.get('concept','')).strip()
    if not concept: raise HTTPException(400,'concept is required')
    try:
        return media_pipeline.prepare(concept,req.get('mode','video'),req.get('style',''),int(req.get('shot_limit',8)),req.get('references') or [])
    except Exception as e:
        raise HTTPException(400,str(e))

@app.post('/api/media/preflight')
def media_preflight(req:dict):
    plan=req.get('plan')
    if not isinstance(plan,dict): raise HTTPException(400,'plan object is required')
    return media_quality.preflight(plan)

@app.post('/api/media/manifest')
def media_manifest(req:dict):
    plan=req.get('plan')
    if not isinstance(plan,dict): raise HTTPException(400,'plan object is required')
    return media_quality.manifest(plan,list(req.get('results') or []))

@app.post('/api/media/produce')
def media_produce(req:dict):
    plan=req.get('plan')
    if not isinstance(plan,dict): raise HTTPException(400,'plan object is required')
    jid=jobs.create('media_production',{'plan':plan,'provider':req.get('provider'),'concurrency':req.get('concurrency',3),'chain_references':req.get('chain_references',True)},max_attempts=2)
    return {'job_id':jid,'status':'queued','kind':'media_production','shot_count':plan.get('shot_count',0)}

@app.post('/api/media/studio-plan')
def media_studio_plan(req:dict):
    concept=str(req.get('concept','')).strip()
    if not concept: raise HTTPException(400,'concept is required')
    try:
        return media_studio.prepare(concept,req.get('mode','video'),req.get('style',''),int(req.get('shot_limit',8)),req.get('references') or [])
    except Exception as exc: raise HTTPException(400,str(exc))

@app.post('/api/media/studio-preflight')
def media_studio_preflight(req:dict):
    plan=req.get('plan')
    if not isinstance(plan,dict): raise HTTPException(400,'plan object is required')
    return media_studio.preflight(plan)

@app.post('/api/media/studio-render')
def media_studio_render(req:dict):
    plan=req.get('plan')
    if not isinstance(plan,dict): raise HTTPException(400,'plan object is required')
    try:
        jid=jobs.create('media_studio',{'plan':plan,'provider':req.get('provider'),'concurrency':req.get('concurrency',3),'chain_references':req.get('chain_references',True),'max_retries':req.get('max_retries',2)},max_attempts=2)
        return {'job_id':jid,'status':'queued','kind':'media_studio','shot_count':plan.get('shot_count',0)}
    except Exception as exc: raise HTTPException(400,str(exc))

@app.post('/api/media/render-plan')
def media_render_plan(req:dict):
    mode=str(req.get('mode','video'))
    items=list(req.get('items') or [])[:16]
    if not items: raise HTTPException(400,'items are required')
    return {'job_id':jobs.create('media_batch',{'mode':mode,'items':items},max_attempts=2),'status':'queued','item_count':len(items)}

@app.post('/api/media/image')
def media_image(req:MediaGenerateRequest):
    jid=jobs.create('media_image',req.model_dump(),max_attempts=2)
    return {'job_id':jid,'status':'queued','kind':'image_generation'}

@app.post('/api/media/video')
def media_video(req:MediaGenerateRequest):
    jid=jobs.create('media_video',req.model_dump(),max_attempts=2)
    return {'job_id':jid,'status':'queued','kind':'video_generation'}

@app.post('/api/media/edit')
def media_edit(req:MediaEditRequest):
    jid=jobs.create('media_edit',req.model_dump(),max_attempts=2)
    return {'job_id':jid,'status':'queued','kind':'media_edit'}

@app.get('/api/media/jobs')
def media_jobs():
    return [x for x in jobs.list() if str(x.get('kind','')).startswith('media_')]

@app.get('/api/situational/signals')
def situational_signals(limit:int=50): return situational_store.list_signals(limit)

@app.get('/api/automations')
def list_automations(): return automation.list()
@app.post('/api/automations')
def create_automation(req:AutomationRequest): return {'id':automation.create(req.name,req.objective,req.interval_minutes)}
@app.post('/api/automations/{automation_id}/enable')
def set_automation(automation_id:str,enabled:bool=True): automation.set_enabled(automation_id,enabled); return {'ok':True}
@app.post('/api/export')
def export_data(destination:str='exports'): return {'path':ExportManager(settings.data_root).export(destination)}
@app.get('/api/avatar/manifest')
def avatar_manifest():
    root=Path(__file__).resolve().parents[2]
    return {'manifest':load_avatar_manifest(root), 'runtime':avatar_runtime_info(root/'frontend')}

@app.get('/api/avatar/health')
def avatar_health():
    root=Path(__file__).resolve().parents[2]
    info=avatar_runtime_info(root/'frontend')
    return {'ok': bool(info.get('model',{}).get('installed') and info.get('validation',{}).get('valid')), **info}

@app.get('/api/avatar/state')
def avatar_state():
    return avatar_controller.get()

@app.post('/api/avatar/state')
def avatar_set_state(state: str, emotion: str = 'neutral', action: str = '', hint: str = '', speech_level: float = 0.0, source: str = 'api'):
    try:
        return avatar_controller.set(state, emotion=emotion, action=action or None, hint=hint, speech_level=speech_level, source=source)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.post('/api/avatar/appearance')
def avatar_set_appearance(appearance: str, request: Request):
    try:
        value=avatar_controller.set_appearance(appearance, source='admin' if getattr(request.state, 'admin', False) else 'ui')
        ui_preferences.update({'appearance': value['appearance']})
        return value
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.post('/api/avatar/motion')
def avatar_set_motion(motion: str = 'full'):
    try: return avatar_controller.set_motion(motion)
    except ValueError as exc: raise HTTPException(400, str(exc))

@app.get('/api/avatar/profiles')
def avatar_profiles():
    manifest=load_avatar_manifest(Path(__file__).resolve().parents[2])
    return {'appearances': APPEARANCES, 'emotions': manifest.get('emotions', []), 'actions': manifest.get('actions', [])}

@app.get('/api/preferences')
def get_preferences():
    return ui_preferences.get()

@app.patch('/api/preferences')
def patch_preferences(payload: dict):
    if not isinstance(payload, dict): raise HTTPException(400, 'Preferences payload must be an object.')
    return ui_preferences.update(payload)

@app.get('/assets/catalyst/{name:path}')
def catalyst_asset(name: str):
    root=(Path(__file__).resolve().parents[2]/'frontend'/'assets'/'catalyst').resolve()
    path=(root/Path(name)).resolve()
    if root != path and root not in path.parents: raise HTTPException(404,'Unknown Catalyst asset')
    if not path.is_file(): raise HTTPException(404,'Unknown Catalyst asset')
    return FileResponse(path)

@app.get('/')
def home(): return FileResponse(Path(__file__).resolve().parents[2]/'frontend'/'index.html')

@app.get('/catalyst-vrm.js')
def catalyst_vrm_js():
    return FileResponse(Path(__file__).resolve().parents[2]/'frontend'/'catalyst-vrm.js', media_type='application/javascript')

@app.get('/catalyst-app.js')
def catalyst_app_js():
    return FileResponse(Path(__file__).resolve().parents[2]/'frontend'/'catalyst-app.js', media_type='application/javascript')

@app.get('/catalyst-ui.css')
def catalyst_ui_css():
    return FileResponse(Path(__file__).resolve().parents[2]/'frontend'/'catalyst-ui.css', media_type='text/css')

@app.get('/catalyst-phase8.css')
def catalyst_phase8_css():
    return FileResponse(Path(__file__).resolve().parents[2]/'frontend'/'catalyst-phase8.css', media_type='text/css')

@app.get('/catalyst-avatar.css')
def catalyst_css():
    return FileResponse(Path(__file__).resolve().parents[2]/'frontend'/'catalyst-avatar.css', media_type='text/css')

@app.get('/manifest.json')
def manifest_file(): return FileResponse(Path(__file__).resolve().parents[2]/'frontend'/'manifest.json',media_type='application/manifest+json')

@app.get('/sw.js')
def service_worker(): return FileResponse(Path(__file__).resolve().parents[2]/'frontend'/'sw.js',media_type='application/javascript')

@app.get('/icon.svg')
def icon_file(): return FileResponse(Path(__file__).resolve().parents[2]/'frontend'/'icon.svg',media_type='image/svg+xml')
