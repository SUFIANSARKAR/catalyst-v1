from pathlib import Path
from catalyst.analysis import DataAnalysisEngine
from catalyst.projects.compiler import ProjectMemoryCompiler
from catalyst.tasks.store import TaskStore
from catalyst.sessions.store import SessionStore

def test_project_index_and_search(tmp_path):
    ws=tmp_path/'ws'; ws.mkdir(); (ws/'main.py').write_text('def catalyst_router():\n    return "engineering reasoning memory"\n',encoding='utf-8')
    eng=DataAnalysisEngine(str(ws),str(tmp_path/'data')); out=eng.index_project()
    assert out['total_files']==1 and out['chunks']>=1
    assert eng.search('reasoning memory')
    eng.chunks.close()

def test_project_memory_compiler(tmp_path):
    ws=tmp_path/'demo'; ws.mkdir(); (ws/'README.md').write_text('# Demo\n\nDecision: use persistent memory\nExperiment: benchmark\nTODO: fix indexing\n',encoding='utf-8')
    out=ProjectMemoryCompiler(str(ws),str(tmp_path/'memory')).compile()
    project=Path(tmp_path/'memory'/'projects'/'demo')
    assert out['files']==1 and (project/'overview.md').exists() and (project/'decisions.md').read_text().find('Decision:')>=0

def test_task_dependencies(tmp_path):
    tasks=TaskStore(str(tmp_path/'tasks.db'))
    parent=tasks.create('parent'); child=tasks.create('child',depends_on=[parent])
    claimed=tasks.claim(); assert claimed['id']==parent
    tasks.update(parent,'completed','done')
    claimed2=tasks.claim(); assert claimed2['id']==child
    tasks.close()

def test_session_cancel(tmp_path):
    s=SessionStore(str(tmp_path/'sessions')); sid=s.create('x'); assert not s.is_cancelled(sid); s.cancel(sid); assert s.is_cancelled(sid); s.close()
