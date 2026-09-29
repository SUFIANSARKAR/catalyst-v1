import json
from catalyst.engineering.tools import EngineeringToolbox
from catalyst.engineering.agent import EngineeringAgent


def test_engineering_toolbox_real_repo_tools(tmp_path):
    (tmp_path / "app.py").write_text("def greet():\n    return 'hello'\n")
    box = EngineeringToolbox(str(tmp_path), str(tmp_path / "data"))
    m = box.repo_map()
    assert m["file_count"] == 1
    r = box.read_file("app.py")
    assert "greet" in r["content"]
    hit = box.search_code("greet")
    assert hit["hits"][0]["line"] == 1


def test_engineering_agent_uses_tools_and_stops_on_approval(tmp_path):
    (tmp_path / "app.py").write_text("def greet():\n    return 'hello'\n")
    calls = []
    def model(messages, tools):
        calls.append((messages, tools))
        if len(calls) == 1:
            return {"content": "", "tool_calls": [{"id":"1", "type":"function", "function":{"name":"read_file","arguments":json.dumps({"path":"app.py"})}}]}
        return {"content": "Need to modify app.py; requesting approval for the mutation.", "tool_calls": [{"id":"2", "type":"function", "function":{"name":"write_file","arguments":json.dumps({"path":"app.py","content":"def greet():\n    return 'hi'\n"})}}]}
    agent = EngineeringAgent(str(tmp_path), model=model, max_iterations=4, data_root=str(tmp_path / 'data'))
    run = agent.run("Change greeting", execute=False, approval=False)
    assert run.status == 'awaiting_approval'
    assert len(calls) == 2
    assert run.tool_calls == 1
    assert run.pending_approval[0]['tool'] == 'write_file'
    assert (tmp_path / 'app.py').read_text() == "def greet():\n    return 'hello'\n"
