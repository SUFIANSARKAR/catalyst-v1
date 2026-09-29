from pathlib import Path

def test_model_catalog_and_switcher_present():
    api=Path('catalyst/api/server.py').read_text()
    ui=Path('frontend/index.html').read_text()
    for name in ['GPT-5.6 Sol','GPT-5.6 Luna','Qwen 2.5 72B','Qwen 2.5 14B','DeepSeek-V3','DeepSeek-Coder','Mistral Large 2']:
        assert name in api
    assert '/api/models/catalog' in ui
    assert 'modelgrid' in ui
    assert 'prefillModel' in ui
