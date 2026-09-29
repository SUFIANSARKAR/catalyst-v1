from __future__ import annotations
from typing import Any
from .version import __version__


def manifest(settings, gateway, tools, agents, plugins, media, job_worker, policy, audio=None, identity=None) -> dict[str, Any]:
    p=gateway.active_profile
    caps=set(p.capabilities if p else ())
    return {
        'protocol':'catalyst.capabilities.v1',
        'version':__version__,
        'core':{
            'chat':True,'streaming_chat':True,'persistent_memory':True,'conversation_compaction':True,
            'project_index':True,'data_analysis':True,'web_research':True,'missions':True,'durable_jobs':True,
            'automations':True,'approvals':True,'provenance':True,'artifacts':True,'evaluation':True,
            'improvement_lab':True,'specialist_agents':True,'multimodal_attachments':True,'creative_studio':True,'semantic_memory':True,'audio_speech':True,'audio_transcription':True,'scoped_identity':True,'long_horizon_evaluation':True,'multi_agent_teams':True,'selector_teams':True,'swarm_handoffs':True,'graph_flows':True,'perception_store':True,'browser_computer_use':True,'playwright_executor':True,'temporal_world_model':True,'working_memory':True,'mission_recovery':True,'mission_checkpoints':True,'realtime_voice_transport':True,'evidence_research':True,'research_claim_capture':True,'research_conflict_signals':True,'safe_self_improvement_lab':True,'isolated_improvement_experiments':True,'explicit_promotion_rollback':True,'device_registry':True,'desktop_shell_bridge':True,'android_shell_bridge':True,'device_control_plane':True,'device_command_queue':True,'device_capability_gating':True,'situational_intelligence':True,'event_ingestion':True,'situational_prioritization':True,'mission_stall_detection':True,'proactive_signals':True,'proactive_suggestions':True,'proactive_never_auto_execute':True,'engineering_intelligence_fabric':True,'engineering_capability_catalog':True,'physicsnemo_adapter':True,'pyvista_adapter':True,'unified_capability_fusion':True,'mcp_gateway':True,'browser_dom_perception':True,'dynamic_tool_router':True,'durable_state_checkpoint_store':True,'e2b_sandbox_provider':True,'durable_event_ledger':True,'observation_fusion':True,'real_host_device_executor':True,'device_agent_protocol':True,'adaptive_cognitive_planning':True,'cross_system_result_feedback':True,'local_os_actions':True,'host_device_agent_cli':True,'cognitive_plan_generation':True,'voice_cognitive_turns':True,'engineering_workflow_planner':True,'durable_event_feedback':True,'unified_cognitive_state':True,'continuous_cognitive_loop':True,'persistent_objectives':True,'experience_learning':True,'executive_cognition':True,'persistent_objective_ranking':True,'cognitive_decision_records':True,'recovery_oriented_cycles':True,'autonomous_cognition':True,'continuous_autonomy_scheduler':True,'autonomous_objective_dispatch':True,'autonomous_outcome_reconciliation':True,'adaptive_mission_control':True,'mission_failure_recovery':True,'mission_stall_recovery':True,'engineering_geometry_inspection':True,'adaptive_reasoning_briefs':True,'hypothesis_tracking':True,'evidence_weighted_decisions':True,'uncertainty_estimation':True,'bounded_model_assisted_deliberation':True,'claim_verification':True,'apex_mission_store':True,'apex_state_checkpointing':True,'apex_unified_routing':True,'apex_registered_execution_adapters':True,'device_credential_auth':True,'atomic_device_command_claim':True,'technical_media_quality_inspection':True,'android_companion_client':True,'desktop_companion_client':True,'release_packaging_guard':True,
        },
        'media':{
            'image_generation':bool('image_generation' in caps or media.provider_profiles()),
            'video_generation':bool('video_generation' in caps or media.provider_profiles()),
            'deterministic_editing':True,'story_planning':True,'batch_rendering':True,
        },
        'audio':{
            'speech':bool(audio and any(x.get('supports_speech') for x in audio.providers())),
            'transcription':bool(audio and any(x.get('supports_transcription') for x in audio.providers())),
        },
        'runtime':{
            'shell_enabled':bool(settings.allow_shell),'job_worker_alive':bool(job_worker.thread and job_worker.thread.is_alive()),
            'docker_sandbox':settings.sandbox_mode in {'auto','docker'},'computer_use':True,'computer_use_action_budget':settings.computer_use_max_actions,'computer_use_allowed_domains':settings.computer_use_allowed_domains,'api_auth_enabled':bool(settings.api_token or getattr(settings,'api_tokens',{})),
        },
        'counts':{'tools':len(tools.list()),'agents':len(agents.describe()),'plugins':len(plugins.list())},
        'models':{'configured':bool(p and p.configured),'provider':p.name if p else None,'model':p.model if p else None,'capabilities':sorted(caps)},
        'policy_roles':policy.describe(),
        'identity':identity.describe() if identity else {'enabled':False},
    }
