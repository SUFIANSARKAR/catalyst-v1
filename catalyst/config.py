from dataclasses import dataclass, field
import json, os
from pathlib import Path
from typing import Any

def _int(name, default, minimum, maximum):
    try:v=int(os.getenv(name,str(default)))
    except ValueError:v=default
    return max(minimum,min(v,maximum))

@dataclass
class ProviderProfile:
    name:str; base_url:str; model:str=''; api_key:str=''; kind:str='openai_compatible'; capabilities:tuple[str,...]=(); role:str='general'; options:dict[str,Any]=field(default_factory=dict);
    @property
    def configured(self):return bool(self.api_key and self.model)

@dataclass
class Settings:
    model:str=field(default_factory=lambda:os.getenv('CATALYST_MODEL',''))
    base_url:str=field(default_factory=lambda:os.getenv('CATALYST_BASE_URL','https://api.openai.com/v1'))
    api_key:str=field(default_factory=lambda:os.getenv('CATALYST_API_KEY',''))
    memory_path:str=field(default_factory=lambda:os.getenv('CATALYST_MEMORY_PATH','catalyst_data/memory.db'))
    workspace_root:str=field(default_factory=lambda:os.getenv('CATALYST_WORKSPACE','workspace'))
    data_root:str=field(default_factory=lambda:os.getenv('CATALYST_DATA_ROOT','catalyst_data'))
    secrets_path:str=field(default_factory=lambda:os.getenv('CATALYST_SECRETS_PATH','catalyst_data/secrets.json'))
    users_path:str=field(default_factory=lambda:os.getenv('CATALYST_USERS_PATH','catalyst_data/users.json'))
    max_steps:int=field(default_factory=lambda:_int('CATALYST_MAX_STEPS',16,1,64))
    request_timeout:float=field(default_factory=lambda:float(os.getenv('CATALYST_TIMEOUT','180')))
    temperature:float=field(default_factory=lambda:float(os.getenv('CATALYST_TEMPERATURE','0.2')))
    max_tokens:int=field(default_factory=lambda:_int('CATALYST_MAX_TOKENS',16384,256,65536))
    allow_shell:bool=field(default_factory=lambda:os.getenv('CATALYST_ALLOW_SHELL','false').lower()=='true')
    approval_mode:str=field(default_factory=lambda:os.getenv('CATALYST_APPROVAL_MODE','prompt'))
    max_context_messages:int=field(default_factory=lambda:_int('CATALYST_CONTEXT_MESSAGES',80,10,500))
    context_keep_messages:int=field(default_factory=lambda:_int('CATALYST_CONTEXT_KEEP',40,10,200))
    context_compact_trigger:int=field(default_factory=lambda:_int('CATALYST_CONTEXT_TRIGGER',70,30,500))
    max_tool_output:int=field(default_factory=lambda:_int('CATALYST_MAX_TOOL_OUTPUT',120000,1000,500000))
    embedding_model:str=field(default_factory=lambda:os.getenv('CATALYST_EMBEDDING_MODEL',''))
    sandbox_mode:str=field(default_factory=lambda:os.getenv('CATALYST_SANDBOX_MODE','auto'))
    docker_image:str=field(default_factory=lambda:os.getenv('CATALYST_DOCKER_IMAGE','python:3.12-slim'))
    sandbox_timeout:int=field(default_factory=lambda:_int('CATALYST_SANDBOX_TIMEOUT',120,5,1800))
    max_parallel_agents:int=field(default_factory=lambda:_int('CATALYST_MAX_PARALLEL_AGENTS',4,1,16))
    context_char_budget:int=field(default_factory=lambda:_int('CATALYST_CONTEXT_CHARS',180000,20000,2000000))
    sandbox_memory_mb:int=field(default_factory=lambda:_int('CATALYST_SANDBOX_MEMORY_MB',2048,256,32768))
    sandbox_cpus:float=field(default_factory=lambda:float(os.getenv('CATALYST_SANDBOX_CPUS','2.0')))
    sandbox_pids:int=field(default_factory=lambda:_int('CATALYST_SANDBOX_PIDS',256,32,4096))
    synthesis_model:str=field(default_factory=lambda:os.getenv('CATALYST_SYNTHESIS_MODEL',''))
    automation_poll_seconds:int=field(default_factory=lambda:_int('CATALYST_AUTOMATION_POLL_SECONDS',10,2,300))
    api_token:str=field(default_factory=lambda:os.getenv('CATALYST_API_TOKEN',''))
    cors_origins:list[str]=field(default_factory=lambda:[x.strip() for x in os.getenv('CATALYST_CORS_ORIGINS','http://127.0.0.1:8000,http://localhost:8000').split(',') if x.strip()])
    model_routes:dict=field(default_factory=lambda:json.loads(os.getenv('CATALYST_MODEL_ROUTES','{}')))
    api_admin_token:str=field(default_factory=lambda:os.getenv('CATALYST_ADMIN_TOKEN',''))
    api_tokens:dict=field(default_factory=lambda:json.loads(os.getenv('CATALYST_API_TOKENS','{}') or '{}'))
    auth_subject_header:str=field(default_factory=lambda:os.getenv('CATALYST_AUTH_SUBJECT_HEADER','x-catalyst-subject'))
    metrics_enabled:bool=field(default_factory=lambda:os.getenv('CATALYST_METRICS','true').lower()=='true')
    active_profile_path:str=field(default_factory=lambda:os.getenv('CATALYST_ACTIVE_PROFILE_PATH','catalyst_data/active_profile'))
    tc_url:str=field(default_factory=lambda:os.getenv('CATALYST_TC_URL',''))
    tc_owner_token:str=field(default_factory=lambda:os.getenv('CATALYST_TC_OWNER_TOKEN',''))
    fsc_command:str=field(default_factory=lambda:os.getenv('CATALYST_SELF_CODING_CMD','full-self-coding'))
    fsc_timeout:int=field(default_factory=lambda:_int('CATALYST_FSC_TIMEOUT',3600,30,86400))
    openhands_url:str=field(default_factory=lambda:os.getenv('CATALYST_OPENHANDS_URL',''))
    openhands_runtime_url:str=field(default_factory=lambda:os.getenv('CATALYST_OPENHANDS_RUNTIME_URL',''))
    sweagent_command:str=field(default_factory=lambda:os.getenv('CATALYST_SWEAGENT_CMD','sweagent'))
    sweagent_timeout:int=field(default_factory=lambda:_int('CATALYST_SWEAGENT_TIMEOUT',3600,30,86400))
    memory_auto_consolidate:bool=field(default_factory=lambda:os.getenv('CATALYST_MEMORY_AUTO_CONSOLIDATE','false').lower()=='true')
    memory_consolidate_threshold:int=field(default_factory=lambda:_int('CATALYST_MEMORY_CONSOLIDATE_THRESHOLD',500,50,100000))
    mission_max_steps:int=field(default_factory=lambda:_int('CATALYST_MISSION_MAX_STEPS',24,1,100))
    computer_use_allowed_domains:list[str]=field(default_factory=lambda:[x.strip() for x in __import__('os').getenv('CATALYST_COMPUTER_USE_ALLOWED_DOMAINS','').split(',') if x.strip()])
    computer_use_headless:bool=field(default_factory=lambda:__import__('os').getenv('CATALYST_COMPUTER_USE_HEADLESS','true').lower()=='true')
    computer_use_max_actions:int=field(default_factory=lambda:_int('CATALYST_COMPUTER_USE_MAX_ACTIONS',80,1,500))
    working_memory_chars:int=field(default_factory=lambda:_int('CATALYST_WORKING_MEMORY_CHARS',24000,4000,200000))
    computer_use_require_approval:bool=field(default_factory=lambda:os.getenv('CATALYST_COMPUTER_USE_REQUIRE_APPROVAL','true').lower()=='true')
    mission_replan_on_failure:bool=field(default_factory=lambda:os.getenv('CATALYST_MISSION_REPLAN_ON_FAILURE','true').lower()=='true')
    mission_retry_backoff_seconds:float=field(default_factory=lambda:float(os.getenv('CATALYST_MISSION_RETRY_BACKOFF','1.0')))
    proactive_scan_seconds:int=field(default_factory=lambda:_int('CATALYST_PROACTIVE_SCAN_SECONDS',60,10,3600))
    world_model_path:str=field(default_factory=lambda:__import__('os').getenv('CATALYST_WORLD_MODEL_PATH','catalyst_data/world_model.db'))
    perception_path:str=field(default_factory=lambda:__import__('os').getenv('CATALYST_PERCEPTION_PATH','catalyst_data/perception.db'))
    mind_path:str=field(default_factory=lambda:__import__('os').getenv('CATALYST_MIND_PATH','catalyst_data/mind.db'))
    mind_memory_limit:int=field(default_factory=lambda:_int('CATALYST_MIND_MEMORY_LIMIT',24,8,100))
    cognitive_state_path:str=field(default_factory=lambda:__import__('os').getenv('CATALYST_COGNITIVE_STATE_PATH','catalyst_data/cognitive_state.db'))
    cognitive_episode_limit:int=field(default_factory=lambda:_int('CATALYST_COGNITIVE_EPISODE_LIMIT',12,4,50))
    google_client_id:str=field(default_factory=lambda:os.getenv('CATALYST_GOOGLE_CLIENT_ID',''))
    google_client_secret:str=field(default_factory=lambda:os.getenv('CATALYST_GOOGLE_CLIENT_SECRET',''))
    google_redirect_uri:str=field(default_factory=lambda:os.getenv('CATALYST_GOOGLE_REDIRECT_URI',''))
    google_allowed_domain:str=field(default_factory=lambda:os.getenv('CATALYST_GOOGLE_ALLOWED_DOMAIN',''))
    admin_session_ttl:int=field(default_factory=lambda:_int('CATALYST_ADMIN_SESSION_TTL',43200,300,2592000))
    # Admin unlock security (optional but recommended)
    admin_password_sha256:str=field(default_factory=lambda:os.getenv('CATALYST_ADMIN_PASSWORD_SHA256',''))
    admin_unlock_max_attempts:int=field(default_factory=lambda:_int('CATALYST_ADMIN_UNLOCK_MAX_ATTEMPTS',5,1,50))
    admin_unlock_window_seconds:int=field(default_factory=lambda:_int('CATALYST_ADMIN_UNLOCK_WINDOW_SECONDS',900,10,86400))
    admin_unlock_lockout_seconds:int=field(default_factory=lambda:_int('CATALYST_ADMIN_UNLOCK_LOCKOUT_SECONDS',900,10,86400))
    autonomous_cognition_enabled:bool=field(default_factory=lambda:os.getenv('CATALYST_AUTONOMOUS_COGNITION','false').lower()=='true')
    autonomous_cognition_poll_seconds:int=field(default_factory=lambda:_int('CATALYST_AUTONOMOUS_COGNITION_POLL_SECONDS',60,10,3600))
    autonomous_cognition_auto_dispatch:bool=field(default_factory=lambda:os.getenv('CATALYST_AUTONOMOUS_AUTO_DISPATCH','true').lower()=='true')
    autonomous_cognition_max_cycles:int=field(default_factory=lambda:_int('CATALYST_AUTONOMOUS_MAX_CYCLES',1,1,5))
    adaptive_max_recoveries:int=field(default_factory=lambda:_int('CATALYST_ADAPTIVE_MAX_RECOVERIES',3,1,10))
    adaptive_stall_seconds:int=field(default_factory=lambda:_int('CATALYST_ADAPTIVE_STALL_SECONDS',900,60,86400))
    reasoning_mode:str=field(default_factory=lambda:os.getenv('CATALYST_REASONING_MODE','auto'))
    reasoning_model_calls:int=field(default_factory=lambda:_int('CATALYST_REASONING_MODEL_CALLS',1,0,2))
    # Enhanced personality, privileged tools, and voice output stay behind an
    # explicit Creator Admin unlock by default.
    enhanced_admin_only:bool=field(default_factory=lambda:os.getenv('CATALYST_ENHANCED_ADMIN_ONLY','true').lower() in {'1','true','yes','on'})
    voice_breathing:bool=field(default_factory=lambda:os.getenv('CATALYST_VOICE_BREATHING','true').lower() in {'1','true','yes','on'})
    voice_breath_interval_chars:int=field(default_factory=lambda:_int('CATALYST_VOICE_BREATH_INTERVAL_CHARS',420,120,2000))
    def __post_init__(self):Path(self.data_root).mkdir(parents=True,exist_ok=True);Path(self.workspace_root).mkdir(parents=True,exist_ok=True);Path(self.active_profile_path).parent.mkdir(parents=True,exist_ok=True)
    def load_profiles(self):
        profiles={}
        if self.api_key or self.model:profiles['default']=ProviderProfile('default',self.base_url,self.model,self.api_key)
        p=Path(self.secrets_path)
        if p.exists():
            try:raw=json.loads(p.read_text(encoding='utf-8'))
            except Exception:raw={}
            for name,item in raw.get('profiles',{}).items():
                if isinstance(item,dict):profiles[name]=ProviderProfile(name,str(item.get('base_url','https://api.openai.com/v1')),str(item.get('model','')),str(item.get('api_key','')),str(item.get('kind','openai_compatible')),tuple(item.get('capabilities',[]) or []),str(item.get('role','general')),dict(item.get('options',{}) or {}))
        active=Path(self.active_profile_path)
        if active.exists():
            try:self._active_profile=active.read_text(encoding='utf-8').strip()
            except Exception:self._active_profile=''
        else:self._active_profile=''
        return profiles
    def save_profile(self,profile):
        p=Path(self.secrets_path);p.parent.mkdir(parents=True,exist_ok=True)
        try:raw=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'profiles':{}}
        except Exception:raw={'profiles':{}}
        raw.setdefault('profiles',{})[profile.name]={'base_url':profile.base_url,'model':profile.model,'api_key':profile.api_key,'kind':profile.kind,'capabilities':list(profile.capabilities),'role':profile.role,'options':dict(profile.options or {})}
        p.write_text(json.dumps(raw,indent=2),encoding='utf-8')
        try:os.chmod(p,0o600)
        except OSError:pass
    def save_active_profile(self,name:str):
        p=Path(self.active_profile_path);p.write_text(name,encoding='utf-8')
        try:os.chmod(p,0o600)
        except OSError:pass
