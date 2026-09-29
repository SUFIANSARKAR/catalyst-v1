from pathlib import Path
from catalyst.sessions import SessionStore
from catalyst.plugins import Plugin,PluginRegistry
from catalyst.data.inspector import DatasetInspector


def test_session_summary(tmp_path):
    s=SessionStore(tmp_path/'sessions'); sid=s.create('x'); s.append(sid,'user','hello'); s.set_summary(sid,'Project goals'); assert s.get_summary(sid)=='Project goals'

def test_plugin_registry():
    r=PluginRegistry(); r.register(Plugin('demo','demo')); r.enable('demo'); assert r.list()[0]['enabled'] is True

def test_jsonl_inspector(tmp_path):
    (tmp_path/'a.jsonl').write_text('{"x":1}\n{"x":2}\n',encoding='utf-8'); out=DatasetInspector(tmp_path).inspect('a.jsonl'); assert out['rows_sampled']==2
