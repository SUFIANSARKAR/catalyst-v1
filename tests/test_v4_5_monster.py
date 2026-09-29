import asyncio
from pathlib import Path

from catalyst.engineering.factory import EngineeringProductionFactory
from catalyst.media.production import MediaProductionPipeline
from catalyst.media.quality import MediaQualityController
from catalyst.media.studio import MediaStudio


def test_engineering_factory_prepare_has_parallel_lanes(tmp_path):
    class Repo:
        root = tmp_path
        def repo_map(self): return {'file_count': 1, 'total_lines': 4, 'languages': {'python': 1}, 'largest_files': [{'path':'app.py'}]}
        def dependency_graph(self): return {'hotspots': [], 'edges_sample': []}
    class Tests:
        def plan(self, files): return {'focused': files, 'full':['regression']}
    class Toolbox:
        def context_pack(self, objective, focus_files, max_files=40, max_chars=180000):
            return {'repo': {'file_count':1,'total_lines':4,'languages':{'python':1}}, 'candidate_files':['app.py'], 'hotspots':[], 'test_strategy':{'focused':['app.py']}}
    class Agent:
        toolbox = Toolbox()
        def plan(self, objective):
            class R: plan=[{'id':'implement'}]
            return R()
    plan = EngineeringProductionFactory(Agent()).prepare('fix app')
    assert len(plan['parallel_lanes']) == 3
    assert plan['recovery']['enabled']


def test_engineering_factory_bounds_recovery_cycles():
    class ToolBox: 
        def context_pack(self,*a,**k): return {'repo':{},'candidate_files':[],'hotspots':[],'test_strategy':{}}
    class Run:
        status='needs_replan'; phase='recovery'; run_id='r'; iterations=1; tool_calls=1; evidence=[{'event':'tool','name':'run_tests','result':{'status':'ok','result':{'returncode':1}}}]; final=''
    class Agent:
        toolbox=ToolBox()
        def plan(self, objective):
            class P: plan=[]
            return P()
        def run(self, *args, **kwargs): return Run()
    result=EngineeringProductionFactory(Agent(), max_cycles=2).run('fix', execute=True, approval=True)
    assert len(result.cycles) == 2
    assert result.status == 'needs_replan'


def test_media_studio_assigns_prompt_fingerprints():
    class Planner:
        def plan(self, concept, mode, style, shot_limit):
            return {'title':'T','visual_style':'cinematic','characters':[],'world':{},'scenes':[{'scene':'S','shots':[{'id':'S_SH1','prompt':'hero'}]}],'mode':mode}
    studio = MediaStudio(MediaProductionPipeline(object(), Planner()), MediaQualityController())
    plan=studio.prepare('hero','image')
    shot=plan['scenes'][0]['shots'][0]
    assert shot['prompt_fingerprint']
    assert studio.preflight(plan)['ready']


def test_media_studio_rejects_duplicate_prompt_fingerprints():
    class Planner:
        def plan(self, concept, mode, style, shot_limit):
            return {'title':'T','visual_style':'x','characters':[],'world':{},'scenes':[{'scene':'S','shots':[{'id':'A','prompt':'same'},{'id':'B','prompt':'same'}]}],'mode':mode}
    studio = MediaStudio(MediaProductionPipeline(object(), Planner()), MediaQualityController())
    plan=studio.prepare('x','image')
    out=studio.preflight(plan)
    assert not out['ready']
    assert out['duplicate_prompt_fingerprints'] == 1
