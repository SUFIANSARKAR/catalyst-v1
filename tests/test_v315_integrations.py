import asyncio
from catalyst.integrations.checkpoints import StateCheckpointStore
from catalyst.integrations.tool_router import DynamicToolRouter
from catalyst.browser.dom import DOMPerception
from catalyst.integrations.mcp_gateway import MCPGateway


def test_checkpoint_delta_and_restore(tmp_path):
    s=StateCheckpointStore(str(tmp_path/'cp.db'))
    s.put('x',{'a':1,'b':2})
    r=s.put('x',{'a':3})
    assert r['delta']=={'set':{'a':3},'remove':['b']}
    assert s.restore('x',1)=={'a':3}

def test_tool_router_top_k():
    r=DynamicToolRouter(top_k=1)
    r.index([
        {'type':'function','function':{'name':'open_url','description':'open a web page'}},
        {'type':'function','function':{'name':'get_weather','description':'weather forecast'}},
    ])
    assert r.rank('open website')[0]['name']=='open_url'

def test_mcp_gateway_registration():
    g=MCPGateway(allowed_servers={'x'})
    g.register_stdio('x','python -c "print(1)"',env={'SAFE':'1'})
    assert 'x' in g._servers

def test_dom_perception_js_present():
    assert 'querySelectorAll' in DOMPerception.JS
