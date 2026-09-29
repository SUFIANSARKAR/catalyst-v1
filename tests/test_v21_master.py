from catalyst.security import PolicyEngine,Principal
from catalyst.evals import EvaluationHarness

def test_policy():
 p=PolicyEngine(); assert p.allowed(Principal(role='creator'),'admin'); assert not p.allowed(Principal(role='researcher'),'shell')

def test_eval_harness(tmp_path):
 e=EvaluationHarness(tmp_path/'evals'); r=e.run([{'id':'a'}],lambda t:{'ok':1}); assert r['passed']==1 and (tmp_path/'evals').exists()
