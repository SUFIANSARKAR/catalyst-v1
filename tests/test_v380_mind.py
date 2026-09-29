from pathlib import Path
from catalyst.memory.store import MemoryStore
from catalyst.mind import CatalystMind


def test_permanent_memory_survives_reopen(tmp_path):
    memory=MemoryStore(str(tmp_path/'memory.db'))
    mind=CatalystMind(str(tmp_path/'mind.db'),memory)
    ids=mind.extract_explicit('Remember that Catalyst must preserve existing systems.', 's1')
    assert ids
    stats=mind.stats()
    assert stats['permanent'] >= 1
    mind.close(); memory.close()
    memory2=MemoryStore(str(tmp_path/'memory.db'))
    mind2=CatalystMind(str(tmp_path/'mind.db'),memory2)
    rows=mind2.search('Catalyst preserve existing systems')
    assert rows and rows[0]['pinned'] is True
    mind2.close(); memory2.close()


def test_secret_is_not_persisted(tmp_path):
    memory=MemoryStore(str(tmp_path/'memory.db'))
    mind=CatalystMind(str(tmp_path/'mind.db'),memory)
    ids=mind.extract_explicit('Remember API_KEY=supersecretvalue', 's1')
    assert not ids
    assert mind.stats()['total'] == 0
    mind.close(); memory.close()
