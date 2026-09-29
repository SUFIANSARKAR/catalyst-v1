from pathlib import Path
from catalyst.engineering.mission import EngineeringMissionController
from catalyst.media.quality import MediaQualityController
class Repo:
 root=Path('.')
 def repo_map(self): return {'largest_files':[{'path':'src/app.py'}]}
 def dependency_graph(self): return {'hotspots':[],'edges_sample':[{'source':'tests/test_app.py','target':'src/app.py'}]}
class Tests:
 def plan(self,files): return {'focused':list(files),'full':['regression']}
def test_mission():
 m=EngineeringMissionController(Repo(),Tests()).prepare('refactor app',['src/app.py'])
 assert [x['id'] for x in m.stages]==['understand','design','implement','verify','impact','review','recover']
def test_reconcile():
 c=EngineeringMissionController(Repo(),Tests()); m=c.prepare('fix'); out=c.reconcile(m,['src/app.py'],[{'returncode':0}],'diff'); assert not out['needs_recovery']
def test_media():
 q=MediaQualityController(); p={'mode':'video','scenes':[{'shots':[{'id':'S1','prompt':'hero','duration':5,'continuity_contract':{'rules':[]}}]}]}; assert q.preflight(p)['ready']; assert q.manifest(p,[{'shot':'S1','outputs':[{'name':'x'}]}])['coverage_complete']
