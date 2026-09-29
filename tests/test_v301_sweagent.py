import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from catalyst.config import Settings
from catalyst.integrations import SWEAgentIntegration, IntegrationFabric

def test_swe_agent_descriptor():
    s=SWEAgentIntegration(command='definitely-not-installed-catalyst')
    d=s.descriptor()
    assert d['provider']=='swe_agent'
    assert 'issue-solving' in d['capabilities']
    assert d['source_note']

def test_swe_agent_unconfigured_is_safe():
    r=SWEAgentIntegration(command='definitely-not-installed-catalyst').run(repo_path='.')
    assert r.status=='unconfigured'

def test_fabric_contains_swe_agent():
    f=IntegrationFabric(Settings(sweagent_command='definitely-not-installed-catalyst'))
    names={x['name'] for x in f.describe()}
    assert 'swe_agent' in names
