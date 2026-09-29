from pathlib import Path

from catalyst.avatar import AvatarController, AVATAR_STATES, EMOTIONS, avatar_runtime_info


def test_avatar_controller_defaults_to_idle():
    a = AvatarController()
    state = a.get()
    assert state["state"] == "idle"
    assert state["emotion"] == "neutral"
    assert state["appearance"] == "signature"


def test_avatar_controller_accepts_all_states_and_emotions():
    a = AvatarController()
    for state in AVATAR_STATES:
        for emotion in EMOTIONS:
            out = a.set(state, emotion=emotion, speech_level=2)
            assert out["state"] == state
            assert out["emotion"] == emotion
            assert out["speech_level"] == 1


def test_avatar_controller_rejects_invalid_values():
    a = AvatarController()
    try:
        a.set("not-a-state")
        assert False
    except ValueError:
        pass
    try:
        a.set("idle", emotion="not-an-emotion")
        assert False
    except ValueError:
        pass


def test_avatar_controller_appearance_switches():
    a=AvatarController()
    out=a.set_appearance("focus")
    assert out["appearance"] == "focus"
    try:
        a.set_appearance("unknown")
        assert False
    except ValueError:
        pass


def test_runtime_info_reports_model_slot(tmp_path: Path):
    root = tmp_path / "frontend"
    (root / "assets" / "catalyst").mkdir(parents=True)
    info = avatar_runtime_info(root)
    assert info["renderer"] == "vrm-1.0"
    assert info["model"]["installed"] is False
    assert info["fallback"].endswith("avatar_01.png")
