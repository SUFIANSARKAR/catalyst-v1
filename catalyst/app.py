from pathlib import Path
from .config import Settings,ProviderProfile
from .providers import ModelGateway
from .memory import MemoryStore
from .sessions import SessionStore
from .analysis import DataAnalysisEngine
from .tools.safe_paths import WorkspaceGuard
from .tools.builtin import build_tools
from .agents import AgentRegistry
from .core import Catalyst
from .improvement import ImprovementManager
from .research import ResearchEngine
from .projects.compiler import ProjectMemoryCompiler
from .tasks.store import TaskStore
from .audit.store import AuditStore
from .automation import AutomationStore
from .jobs.store import JobStore
from .provenance.store import ProvenanceStore
from .export import ExportManager
from .analysis.artifacts import ArtifactStore
from .agents.executor import AgentExecutionManager
from .jobs.worker import JobWorker
from .jobs.handlers import JobHandlers
from .integrations import IntegrationFabric
from .approvals import ApprovalStore
from .missions import MissionStore
from .attachments import AttachmentStore
from .version import __version__
from .memory.semantic import SemanticMemoryBridge
from .audio import AudioEngine
from .long_horizon import LongHorizonEvaluator
from .teams import TeamEngine
from .world_model import WorldModel
from .perception import PerceptionStore
from .computer_use import PlaywrightComputerUse, ComputerUsePolicy
from .memory.working import WorkingMemory
from .mind import CatalystMind
from .proactive import SituationalStore, SituationalEngine
from .security import PolicyEngine
from .identity_auth import IdentityAuthority
from .observability import ObservabilityStore
from .cognitive import CognitiveStateStore, CognitiveLoop
from .executive import CognitiveExecutive
from .autonomy import AutonomousCognition, AutonomousCognitionDaemon
from .adaptive import AdaptiveMissionController
from .learning import LearningLedger

def create_runtime():
    s=Settings();
    memory=MemoryStore(s.memory_path); sessions=SessionStore(); workspace=WorkspaceGuard(s.workspace_root); analysis=DataAnalysisEngine(s.workspace_root,s.data_root); research=ResearchEngine(s.data_root); compiler=ProjectMemoryCompiler(s.workspace_root,'catalyst_data/memory'); tasks=TaskStore('catalyst_data/tasks.db'); audit=AuditStore('catalyst_data/audit.db'); automation=AutomationStore('catalyst_data/automations.db'); jobs=JobStore('catalyst_data/jobs.db'); provenance=ProvenanceStore('catalyst_data/provenance.db'); artifacts=ArtifactStore('catalyst_data/artifacts'); attachments=AttachmentStore(s.data_root); approvals=ApprovalStore('catalyst_data/approvals.db'); missions=MissionStore('catalyst_data/missions.db');
    observability=ObservabilityStore('catalyst_data/observability.db'); cognitive_state=CognitiveStateStore(s.cognitive_state_path); executive=None; gateway=ModelGateway(s,observability); agents=AgentRegistry(); team_engine=TeamEngine(gateway,agents,s,audit); world_model=WorldModel(s.world_model_path); perception=PerceptionStore(s.perception_path); computer_use=PlaywrightComputerUse(s.data_root,ComputerUsePolicy(s.computer_use_allowed_domains,s.computer_use_max_actions),headless=s.computer_use_headless); working_memory=WorkingMemory(Path(s.data_root)/'working_memory.json',s.working_memory_chars); mind=CatalystMind(s.mind_path,memory); mind.ensure_core_identity(); learning=LearningLedger(Path(s.data_root)/'learning.db'); integrations=IntegrationFabric(s); policy=PolicyEngine(); identity=IdentityAuthority(s,policy); artifacts=artifacts; media=__import__('catalyst.media',fromlist=['MediaEngine']).MediaEngine(s,artifacts,attachments,audit); audio=AudioEngine(s,gateway,artifacts,attachments); semantic=SemanticMemoryBridge(memory,gateway,s); long_horizon=LongHorizonEvaluator();
    agent_executor=AgentExecutionManager(agents,s.workspace_root,s.data_root,audit,s,gateway,integrations);
    situational_store=SituationalStore(Path(s.data_root)/'situational.db'); situational=SituationalEngine(situational_store,world_model,missions,automation,None);
    tools=build_tools(workspace,s.allow_shell,analysis,research,compiler,tasks,agent_executor); cognitive_loop=None; c=Catalyst(gateway,memory,tools,agents,s,sessions,analysis,tasks,audit,compiler,research,automation,agent_executor,attachments=attachments,approvals=approvals,semantic_memory=semantic,world_model=world_model,working_memory=working_memory,computer_use=computer_use,perception=perception,situational=situational,mind=mind,learning=learning); cognitive_loop=CognitiveLoop(mind, c.knowledge, working_memory, cognitive_state, situational, world_model); c.cognitive_loop=cognitive_loop; executive=CognitiveExecutive('catalyst_data/executive.db',cognitive_state,mind,situational,missions); autonomy=AutonomousCognition('catalyst_data/autonomy.db',executive,mind,cognitive_state,situational,missions,jobs,s.autonomous_cognition_max_cycles); adaptive=AdaptiveMissionController('catalyst_data/adaptive_missions.db',missions,jobs,mind,cognitive_state,situational,gateway,getattr(s,'adaptive_max_recoveries',3),getattr(s,'adaptive_stall_seconds',900)); autonomy_daemon=AutonomousCognitionDaemon(autonomy,s.autonomous_cognition_poll_seconds,s.autonomous_cognition_enabled);
    job_handlers=JobHandlers(c,analysis,compiler,agent_executor,provenance,artifacts,missions,media); job_worker=JobWorker(jobs,job_handlers,s.automation_poll_seconds,automation)
    return locals()

def main():
    rt=create_runtime();rt['integration_fabric']=IntegrationFabric(rt['s']);rt['job_worker'].start();rt['autonomy_daemon'].start();s=rt['s'];memory=rt['memory'];sessions=rt['sessions'];workspace=rt['workspace'];analysis=rt['analysis'];gateway=rt['gateway'];c=rt['c'];tasks=rt['tasks'];improvements=ImprovementManager('.');
    sid=sessions.create('Creator workspace')
    print(f'Catalyst {__version__} — personal AI operating layer, native integrations, missions, evidence, automation, media')
    try:
        while True:
            try:text=input('\nYou > ').strip()
            except (EOFError,KeyboardInterrupt):print();break
            if not text:continue
            if text.lower() in {'/quit','/exit','quit','exit'}:break
            if text=='/help':print('/help /status /providers /use <name> /sessions /new /index /search <q> /analyze <file> /compile-memory /tasks /goal <objective> /research <q> /propose <change> /quit');continue
            if text=='/status':
                p=gateway.active_profile;print(f'version={__version__}\nmodel={p.model if p else "<unset>"}\nprovider={p.name if p else "<unset>"}\nworkspace={workspace.root}\ntools={len(rt["tools"].list())}\ntasks={len(tasks.list())}');continue
            if text=='/providers':
                for p in gateway.list_profiles():print(p)
                continue
            if text.startswith('/use '):gateway.activate(text[5:].strip());print(f'Active model: {gateway.active_profile.model}');continue
            if text=='/sessions':print('\n'.join(f'{x["id"][:8]} {x["title"]}' for x in sessions.list()) or 'No sessions');continue
            if text=='/new':sid=sessions.create('New conversation');print(f'Started session {sid[:8]}');continue
            if text=='/index':print(analysis.index_project());continue
            if text.startswith('/search '):print(analysis.search(text[8:]));continue
            if text.startswith('/analyze '):print(analysis.analyze_file(text[9:].strip()));continue
            if text=='/compile-memory':print(rt['compiler'].compile());continue
            if text=='/tasks':print(tasks.list());continue
            if text.startswith('/research '):print(rt['research'].research(text[10:].strip()));continue
            if text.startswith('/goal '):print('\nCatalyst >',c.goal(text[6:],session_id=sid).answer);continue
            if text.startswith('/propose '):print('Proposal created:',improvements.propose(text[9:]));continue
            try:
                result=c.respond(text,session_id=sid);print('\nCatalyst >',result.answer);print(f'[steps={result.steps} tools={", ".join(result.tools_used)} verified={result.verified}]')
            except Exception as exc:print(f'\nCatalyst > Creator Sir, I hit a runtime/setup issue: {exc}')
    finally:
        rt['autonomy_daemon'].stop();rt['job_worker'].stop()
        for x in ('memory','sessions','tasks','audit','automation','jobs','provenance','approvals','missions','world_model','perception','mind','cognitive_state','executive'):
            try: rt[x].close()
            except Exception: pass
        rt['computer_use'].close_all(); rt['observability'].close(); rt['semantic'].close(); rt['long_horizon'].close()
