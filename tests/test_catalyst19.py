import json
from pathlib import Path
from catalyst.attachments import AttachmentStore
from catalyst.artifacts import ArtifactStore
from catalyst.agents.registry import AgentRegistry

def test_attachment_roundtrip(tmp_path):
    store=AttachmentStore(str(tmp_path))
    x=store.save('hello.txt',b'hello world','text/plain')
    part,text=store.to_message_part(x['id'])
    assert 'hello world' in part['text']
    assert text=='hello world'

def test_artifact_metadata(tmp_path):
    store=ArtifactStore(tmp_path)
    x=store.write_json('result.json',{'ok':True})
    assert x['name']=='result.json' and x['sha256']
    assert store.list()[0]['name']=='result.json'

def test_registry_general_and_capabilities():
    r=AgentRegistry()
    assert r.choose('analyze this dataset')=='analyst'
    assert r.choose('research papers about agents')=='research'
    assert r.choose('write a Python function')=='general'  # no external coding adapter configured
    assert 'capabilities' in r.describe()[0]
