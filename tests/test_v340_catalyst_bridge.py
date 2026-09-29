import json
from pathlib import Path
from catalyst.world_model import WorldModel
from catalyst.computer_use import ComputerUsePolicy, BrowserSessionStore
from catalyst.missions import MissionStore
from catalyst.long_horizon import LongHorizonEvaluator


def test_world_model_history_is_temporal(tmp_path):
    g=WorldModel(str(tmp_path/'world.db'))
    g.relate('Tony','uses','Catalyst',confidence=.7,source='a')
    g.relate('Tony','uses','Catalyst',confidence=.9,source='b')
    assert len(g.facts('Tony')) == 1
    assert len(g.facts('Tony',include_history=True)) == 2
    g.close()


def test_browser_session_metadata_persists(tmp_path):
    s=BrowserSessionStore(str(tmp_path/'sessions.db'))
    s.create('abc','https://example.com',{'mission':'m1'})
    s.update('abc',action_count=4)
    row=s.get('abc')
    assert row['action_count']==4 and row['metadata']['mission']=='m1'
    s.close('abc'); assert s.get('abc')['status']=='closed'
    s.shutdown()


def test_policy_requires_both_coordinate_values():
    p=ComputerUsePolicy()
    assert not p.validate({'action':'click','x':10})[0]
    assert p.validate({'action':'click','x':10,'y':20})[0]


def test_mission_dependencies_gate_next_step(tmp_path):
    m=MissionStore(str(tmp_path/'m.db')); mid=m.create('dep')
    m.add_step(mid,1,'one','chat',{'depends_on':[]})
    m.add_step(mid,2,'two','chat',{'depends_on':['s1']})
    assert m.next_step(mid)['seq']==1
    m.update_step(m.steps(mid)[0]['id'],'completed',{'ok':True})
    assert m.next_step(mid)['seq']==2
    m.close()


def test_long_horizon_retry_and_checkpoint(tmp_path):
    e=LongHorizonEvaluator(str(tmp_path/'eval.db')); calls={'n':0}
    def ex(step,seq,prev):
        calls['n']+=1
        return {'ok':calls['n']>1}
    report=e.run({'name':'retry','steps':[{'id':'s1','expect':{'ok':True},'max_attempts':2}]},ex)
    assert report['status']=='passed'
    assert report['steps'][0]['attempt']==2
    assert report['checkpoint']['seq']==1
    e.close()
