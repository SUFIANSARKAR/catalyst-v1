from pathlib import Path
from catalyst.config import Settings, ProviderProfile
from catalyst.sessions import SessionStore
from catalyst.analysis import DataAnalysisEngine


def test_session_persistence(tmp_path):
    s = SessionStore(str(tmp_path / "sessions"))
    sid = s.create("x"); s.append(sid, "user", "hello"); s.append(sid, "assistant", "hey Creator Sir")
    assert [x["content"] for x in s.read(sid)] == ["hello", "hey Creator Sir"]
    s.close()


def test_data_analysis_csv(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir(); (ws / "a.csv").write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    eng = DataAnalysisEngine(str(ws), str(tmp_path / "data")); out = eng.analyze_file("a.csv")
    assert out["columns"] == ["x", "y"] and out["rows_sampled"] == 2


def test_provider_profile():
    p = ProviderProfile("OpenAI", "https://api.openai.com/v1", "gpt", "key")
    assert p.configured
