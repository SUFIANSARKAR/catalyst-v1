from pathlib import Path
from catalyst.teams import TeamEngine, TeamMember

def test_team_modes_and_protocol():
    assert TeamEngine.MODES == {'selector','round_robin','swarm','graph'}
    t=TeamMember('planner','Planner','plan')
    assert t.name == 'planner'

def test_api_exposes_team_engine():
    s=Path('catalyst/api/server.py').read_text()
    assert '/api/teams/run' in s
    assert "mode:str='selector'" in s

def test_capabilities_expose_team_features():
    s=Path('catalyst/capabilities.py').read_text()
    for x in ['multi_agent_teams','selector_teams','swarm_handoffs','graph_flows']:
        assert x in s
