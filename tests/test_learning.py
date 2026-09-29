from catalyst.learning import LearningLedger


def test_learning_only_accepts_observable_or_verified_outcomes(tmp_path):
    ledger = LearningLedger(str(tmp_path / "learning.db"))
    assert ledger.record_outcome("What is the plan?", "Unverified prose") is None
    event = ledger.record_outcome(
        "Fix the repository test failure",
        "The test suite passed after the import was corrected.",
        verified=True,
        tools=["run_tests"],
    )
    assert event
    assert ledger.stats()["verified"] == 1
    assert ledger.search("repository test")
    assert "engineering" in ledger.self_evaluation()["stats"]["by_domain"]


def test_learning_redacts_secrets_and_survives_reopen(tmp_path):
    path = tmp_path / "learning.db"
    first = LearningLedger(str(path))
    first.record_outcome(
        "Configure provider",
        "Used API_KEY=super-secret-value and verified the provider health check.",
        verified=True,
        tools=["health_check"],
    )
    first.close()
    second = LearningLedger(str(path))
    rows = second.search("provider")
    assert rows
    assert "super-secret-value" not in rows[0]["outcome"]
    assert "REDACTED SECRET" in rows[0]["outcome"]
