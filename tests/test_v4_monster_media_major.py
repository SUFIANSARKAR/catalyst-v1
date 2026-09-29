from pathlib import Path

from catalyst.engineering.intelligence import EngineeringIntelligence
from catalyst.media.production import MediaProductionPipeline


class FakeRepo:
    root = Path('.')
    def repo_map(self):
        return {'largest_files': [{'path': 'src/main.py'}], 'file_count': 1}
    def dependency_graph(self):
        return {'hotspots':[{'path':'src/main.py','coupling':3}], 'edges_sample':[
            {'source':'src/main.py','target':'src/lib.py'},
            {'source':'tests/test_main.py','target':'src/main.py'},
        ]}


class FakeTests:
    def plan(self, files):
        return {'focused': list(files), 'full': ['regression']}


def test_engineering_context_pack_has_bounded_evidence(tmp_path):
    (tmp_path/'src').mkdir(); (tmp_path/'src/main.py').write_text('print("x")', encoding='utf-8')
    repo = FakeRepo(); repo.root = tmp_path
    info = EngineeringIntelligence(repo, FakeTests())
    pack = info.context_pack('fix main.py', focus_files=['src/main.py'], max_chars=100)
    assert pack['candidate_files'] == ['src/main.py']
    assert pack['excerpts'][0]['path'] == 'src/main.py'


def test_engineering_impact_analysis_and_recovery():
    info = EngineeringIntelligence(FakeRepo(), FakeTests())
    impact = info.impact_analysis(['src/main.py'])
    assert 'src/lib.py' in impact['direct_dependencies']
    assert 'tests/test_main.py' in impact['reverse_dependents']
    recovery = info.recovery_plan('FAILED test_main.py AssertionError')
    assert recovery['category'] == 'test-regression'


def test_media_production_compiles_continuity():
    class Planner:
        def plan(self, concept, mode, style, shot_limit):
            return {'title':'X','visual_style':'neo noir','characters':[{'name':'A','appearance':'red coat','wardrobe':'red coat'}],
                    'world':{'location':'lab','time':'night','lighting':'blue'},
                    'scenes':[{'scene':'S1','shots':[{'id':'S1_SH1','prompt':'walk','camera':'wide'}]}], 'mode':mode}
    pipe = MediaProductionPipeline(object(), Planner())
    plan = pipe.prepare('x', mode='video', references=['ref1'])
    shot = plan['scenes'][0]['shots'][0]
    assert 'CHARACTER BIBLE' in shot['generation_prompt']
    assert shot['references'] == ['ref1']
    assert plan['production_protocol'] == 'catalyst.media-production.v2'
