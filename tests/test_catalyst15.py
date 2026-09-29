from catalyst.core.orchestrator import Catalyst
from catalyst.execution.sandbox import SandboxRunner

def test_merge_stream_tool_calls():
    parts=[
        {'index':0,'id':'x','function':{'name':'read_','arguments':''}},
        {'index':0,'function':{'name':'file','arguments':'{"path":"a'}},
        {'index':0,'function':{'arguments':'"}'}},
    ]
    out=Catalyst._merge_stream_tool_calls(parts)
    assert out[0]['id']=='x'
    assert out[0]['function']['name']=='read_file'
    assert out[0]['function']['arguments']=='{"path":"a"}'

def test_sandbox_rejects_escape(tmp_path):
    root=tmp_path/'workspace'; root.mkdir()
    s=SandboxRunner(root,tmp_path/'data',mode='off')
    try: s.run('echo nope','../')
    except PermissionError: pass
    else: raise AssertionError('escape should be rejected')
