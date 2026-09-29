from catalyst.integrations.tool_router import DynamicToolRouter
from catalyst.reasoning.tool_search import BoundedToolSearch


def test_toolbench_style_schema_retrieval_with_optional_embeddings():
    def embed(texts):
        return [[1.0, 0.0] if 'browser' in t.lower() or 'url' in t.lower() else [0.0, 1.0] for t in texts]
    router = DynamicToolRouter(top_k=1, embedder=embed)
    router.index([
        {'type': 'function', 'function': {'name': 'open_url', 'description': 'open a browser url'}},
        {'type': 'function', 'function': {'name': 'get_weather', 'description': 'weather forecast'}},
    ])
    assert router.rank('browser url')[0]['name'] == 'open_url'


def test_bounded_tool_search_backtracks_from_bad_branch():
    search = BoundedToolSearch(max_depth=3, max_nodes=10, branch_limit=2)
    def candidates(state, depth):
        if depth == 0:
            return [{'name': 'bad', 'priority': 2}, {'name': 'good', 'priority': 1}]
        return []
    def transition(state, action):
        return action['name']
    def validate(state, actions):
        return bool(actions and actions[0]['name'] == 'good')
    result = search.search('start', candidates, transition, validate)
    assert result and result.valid
    assert result.actions[0]['name'] == 'good'
    assert any(x['event'] == 'backtrack' for x in search.trace)
    assert search.nodes_expanded <= 10
