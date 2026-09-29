from catalyst.mind import CatalystMind


def test_core_identity_anchors_are_permanent_and_survive_reopen(tmp_path):
    path = tmp_path / "mind.db"
    first = CatalystMind(str(path))
    ids = first.ensure_core_identity()
    assert len(ids) == 2
    stats = first.stats()
    assert stats["permanent"] == 2
    assert first.search("female Catalyst")[0]["pinned"] is True
    first.close()

    second = CatalystMind(str(path))
    second.ensure_core_identity()
    assert second.stats()["total"] == 2
    context = second.build_context("Catalyst mission")
    assert "Catalyst-level personal AI" in context
    assert "PERMANENT" in context
    second.close()


def test_identity_prompt_contains_catalyst_loop():
    from catalyst.core.identity import DEFAULT_SYSTEM_PROMPT

    assert "understand intent" in DEFAULT_SYSTEM_PROMPT
    assert "verify" in DEFAULT_SYSTEM_PROMPT
    assert "female identity" in DEFAULT_SYSTEM_PROMPT
