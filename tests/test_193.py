import tempfile
from pathlib import Path
from catalyst.missions import MissionStore

def test_mission_status_progress():
    with tempfile.TemporaryDirectory() as d:
        m=MissionStore(str(Path(d)/"m.db")); mid=m.create("test objective"); m.update(mid,"running",checkpoint={"phase":"execution"}); assert m.get(mid)["status"]=="running"; m.update(mid,"completed",result={"ok":True}); assert m.get(mid)["status"]=="completed"; m.close()
