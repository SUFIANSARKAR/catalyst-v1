from catalyst.apex import ApexMissionStore


def test_apex_mission_store_lifecycle(tmp_path):
    store=ApexMissionStore(str(tmp_path/'apex.db'))
    class M:
        mission_id='m1'; objective='test'; state='planned'; created_at='now'; updated_at='now'
        def as_dict(self): return {'mission_id':self.mission_id,'objective':self.objective,'state':self.state}
    m=M()
    store.save(m,event='planned')
    assert store.get('m1')['state']=='planned'
    row=store.transition('m1','running',checkpoint=2,detail='started')
    assert row['state']=='running' and row['checkpoint']==2
    assert store.events('m1')[0]['detail']=='started'
