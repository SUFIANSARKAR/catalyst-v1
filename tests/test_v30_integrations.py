import json
from catalyst.integrations import IntegrationFabric, IntegrationResult, TCIntegration, OpenHandsIntegration, FSCIntegration
from catalyst.config import Settings


def test_integration_descriptors_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv('CATALYST_TC_URL', raising=False)
    monkeypatch.delenv('CATALYST_OPENHANDS_URL', raising=False)
    monkeypatch.setenv('CATALYST_DATA_ROOT', str(tmp_path/'data'))
    monkeypatch.setenv('CATALYST_WORKSPACE', str(tmp_path/'workspace'))
    s=Settings()
    f=IntegrationFabric(s)
    names={x['name'] for x in f.describe()}
    assert {'tc_engineering_ai','full_self_coding','openhands'} <= names
    assert f.health()['tc_engineering_ai']['status']=='unconfigured'


def test_tc_requires_absolute_http_url():
    try:
        TCIntegration('not-a-url')
    except ValueError as exc:
        assert 'absolute http' in str(exc)
    else:
        raise AssertionError('expected invalid URL rejection')


def test_openhands_descriptor():
    x=OpenHandsIntegration('https://example.test/app','https://example.test/runtime')
    d=x.descriptor(); assert d['configured'] is True; assert d['runtime_url'].endswith('/runtime')


def test_fsc_wrapper_is_configurable(tmp_path):
    f=FSCIntegration('printf')
    assert f.configured
    r=f.run(str(tmp_path), config={'x':1}, timeout=3)
    assert r.status in {'completed','failed'}


def test_result_contract():
    r=IntegrationResult('x','ok',task_id='t',events=[{'type':'done'}])
    d=r.as_dict(); assert d['provider']=='x' and d['task_id']=='t'


def test_executor_native_fallbacks(tmp_path):
    from catalyst.agents.registry import AgentRegistry
    from catalyst.agents.executor import AgentExecutionManager
    class FakeResult:
        def as_dict(self): return {'provider':'tc_engineering_ai','status':'completed','answer':'ok'}
    class FakeTC:
        configured=True
        def submit(self, prompt, wait=True): return FakeResult()
    class FakeInt:
        tc=FakeTC()
        fsc=type('F',(),{'configured':False})()
    r=AgentExecutionManager(AgentRegistry(), str(tmp_path), str(tmp_path/'data'), settings=type('S',(),{'sandbox_mode':'auto','docker_image':'python:3.12-slim','sandbox_timeout':2,'sandbox_memory_mb':256,'sandbox_cpus':1,'sandbox_pids':64,'max_parallel_agents':1})(), integrations=FakeInt())
    out=r.run([{'agent':'tc_engineering_ai','description':'do thing','id':'1'}], synthesize=False)['results'][0]
    assert out['provider']=='tc_engineering_ai' and out['status']=='completed'
