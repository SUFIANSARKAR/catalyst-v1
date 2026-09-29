from pathlib import Path
from catalyst.media.quality import MediaQualityController


def test_media_quality_inspects_png(tmp_path):
    # Minimal valid 1x1 PNG.
    png=bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6360000000020001e221bc330000000049454e44ae426082')
    p=tmp_path/'x.png'; p.write_bytes(png)
    q=MediaQualityController().inspect_artifact({'path':str(p),'name':'x.png'},expected_kind='image')
    assert q['exists'] and q['detected_kind']=='image' and q['dimensions']==(1,1) and q['technical_valid']
