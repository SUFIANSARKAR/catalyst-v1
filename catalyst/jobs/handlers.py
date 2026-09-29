import asyncio
import json

class JobHandlers:
    """Bounded handlers for long-running, resumable Catalyst work."""
    def __init__(self,catalyst,analysis,compiler,agent_executor,provenance,artifacts,missions=None,media=None):
        self.catalyst=catalyst; self.analysis=analysis; self.compiler=compiler; self.agent_executor=agent_executor; self.provenance=provenance; self.artifacts=artifacts; self.missions=missions; self.media=media
    def __call__(self,job):
        kind=job['kind']; payload=__import__('json').loads(job['payload'])
        if kind=='index': return self.analysis.index_project()
        if kind=='compile_memory': return self.compiler.compile(payload.get('project_name'))
        if kind=='analysis': return self.analysis.analyze_file(payload['path'],payload.get('max_rows',1000))
        if kind=='goal': return self.catalyst.goal(payload['objective']).__dict__
        if kind=='mission':
            mid=payload.get('mission_id'); objective=payload['objective']
            if self.missions and mid:
                row=self.missions.get(mid)
                if not row:
                    raise ValueError('Unknown mission')
                if row.get('status') == 'cancelled':
                    return {'mission_id': mid, 'objective': objective, 'status': 'cancelled'}
                if row.get('status') == 'paused':
                    return {'mission_id': mid, 'objective': objective, 'status': 'paused', 'resumeable': True, 'steps': self.missions.steps(mid)}
                if row and not self.missions.steps(mid):
                    plan=self.catalyst.plan_mission(objective)
                    plan['steps'] = plan.get('steps',[])[:getattr(self.catalyst.settings,'mission_max_steps',24)]
                    self.missions.update(mid,'running',plan=plan,checkpoint={'phase':'planned'})
                    for i,step in enumerate(plan.get('steps',[]),1): self.missions.add_step(mid,i,step.get('name',f'Step {i}'),step.get('kind','chat'),step)
                else:
                    plan=json.loads(row['plan']) if row and row.get('plan') else None
                while True:
                    current=self.missions.get(mid)
                    if current and current.get('status') == 'cancelled':
                        return {'mission_id':mid,'objective':objective,'status':'cancelled','steps':self.missions.steps(mid)}
                    if current and current.get('status') == 'paused':
                        return {'mission_id':mid,'objective':objective,'status':'paused','resumeable':True,'steps':self.missions.steps(mid)}
                    step=self.missions.next_step(mid)
                    if not step:
                        remaining=[x for x in self.missions.steps(mid) if x['status'] not in {'completed','skipped'}]
                        if remaining:
                            self.missions.update(mid,'failed',error='Mission dependency deadlock: no runnable step remains',checkpoint={'phase':'dependency_deadlock','remaining':[x['seq'] for x in remaining]})
                            raise RuntimeError('Mission dependency deadlock: no runnable step remains')
                        break
                    self.missions.update_step(step['id'],'running')
                    spec=step['payload']; kind2=spec.get('kind','chat'); attempts=max(1,min(int(spec.get('max_attempts',2)),5)); last_error=None
                    for attempt in range(1,attempts+1):
                        self.missions.record_attempt(mid,step,attempt,last_error)
                        try:
                            if kind2=='agent':
                                result=self.agent_executor.run(spec.get('tasks',[]),spec.get('max_workers'))
                            elif kind2=='research':
                                result=self.catalyst.research_engine.research(spec.get('query') or objective, spec.get('limit',6), self.provenance)
                            elif kind2=='analysis':
                                result=self.analysis.analyze_file(spec['path'],spec.get('max_rows',1000))
                            elif kind2=='computer_use':
                                if not getattr(self.catalyst,'computer_use',None): raise RuntimeError('Computer-use runtime is not configured')
                                sid=spec.get('session_id')
                                if not sid:
                                    sid=self.catalyst.computer_use.start(spec.get('url','about:blank'),spec.get('viewport'))
                                obs=self.catalyst.computer_use.observe(sid,step['seq'])
                                action=self.catalyst.computer_use.policy.validate(spec.get('action') or {}, self.catalyst.computer_use._counts.get(sid,0)) if spec.get('action') else None
                                if action and not action[0]: raise PermissionError(action[1])
                                if spec.get('action'):
                                    result=self.catalyst.computer_use.act(sid,spec['action'],require_approval=True,approved=False)
                                    if result.get('status')=='approval_required': raise PermissionError('Computer-use step requires an approved action; use the computer-use API approval path')
                                else:
                                    from ..computer_use import ComputerUsePlanner
                                    planner=ComputerUsePlanner(self.catalyst.provider)
                                    proposed=planner.choose_action(obs,spec.get('goal') or objective)
                                    result={'status':'proposed','session_id':sid,'action':proposed,'observation':obs.__dict__}
                                    if spec.get('execute_approved'):
                                        result=self.catalyst.computer_use.act(sid,proposed,require_approval=True,approved=True)
                                spec['session_id']=sid
                                self.catalyst.perception.add('mission_computer_use','catalyst',result,sid)
                            else:
                                result=self.catalyst.respond(spec.get('task') or spec.get('prompt') or objective,session_id=(row or {}).get('session_id')).__dict__
                            self.missions.update_step(step['id'],'completed',result={'attempt':attempt,'output':result})
                            self.missions.update(mid,'running',checkpoint={'phase':'step_completed','step':step['seq'],'attempt':attempt})
                            last_error=None; break
                        except Exception as exc:
                            last_error=str(exc); self.missions.update_step(step['id'],'retrying',error=last_error,result={'attempt':attempt,'will_retry':attempt<attempts}); self.missions.update(mid,'running',checkpoint={'phase':'step_retry','step':step['seq'],'attempt':attempt,'error':last_error})
                            if attempt==attempts: break
                    if last_error: self.missions.update_step(step['id'],'failed',error=last_error); raise RuntimeError(f'Mission step {step["seq"]} failed after {attempts} attempts: {last_error}')
                steps=self.missions.steps(mid); result={'mission_id':mid,'objective':objective,'steps':steps,'summary':'Mission completed with persisted step evidence.'}
                self.missions.update(mid,'completed',result=result,checkpoint={'phase':'completed'})
                return result
        if kind=='agents': return self.agent_executor.run(payload.get('tasks',[]),payload.get('max_workers'))
        if kind=='media_image':
            if not self.media: raise ValueError('Media engine is not configured')
            return asyncio.run(self.media.generate_image(payload['prompt'],payload.get('provider'),payload.get('references'),payload.get('aspect_ratio','16:9'),payload.get('quality','auto'),payload.get('background','auto'),payload.get('variants',1),payload.get('negative_prompt',''),payload.get('size'),payload.get('output_compression'),payload.get('options') or {}))
        if kind=='media_video':
            if not self.media: raise ValueError('Media engine is not configured')
            return asyncio.run(self.media.generate_video(payload['prompt'],payload.get('provider'),payload.get('references'),payload.get('aspect_ratio','16:9'),payload.get('duration',8),payload.get('resolution','720p'),payload.get('audio',True),payload.get('negative_prompt',''),payload.get('fps'),payload.get('seed'),payload.get('options') or {}))
        if kind=='media_edit':
            if not self.media: raise ValueError('Media engine is not configured')
            return self.media.edit(payload['operation'],payload.get('inputs',[]),payload.get('options') or {})
        if kind=='media_production':
            if not self.media: raise ValueError('Media engine is not configured')
            from ..media.production import MediaProductionPipeline
            from ..media.planner import CreativePlanner
            pipeline=MediaProductionPipeline(self.media, CreativePlanner(self.catalyst.provider))
            payload_plan=payload.get('plan')
            if not isinstance(payload_plan,dict): raise ValueError('media production plan is required')
            return asyncio.run(pipeline.render(payload_plan, provider=payload.get('provider'), concurrency=payload.get('concurrency',3), chain_references=bool(payload.get('chain_references',True))) )
        if kind=='media_studio':
            if not self.media: raise ValueError('Media engine is not configured')
            from ..media.production import MediaProductionPipeline
            from ..media.planner import CreativePlanner
            from ..media.quality import MediaQualityController
            from ..media.studio import MediaStudio
            payload_plan=payload.get('plan')
            if not isinstance(payload_plan,dict): raise ValueError('media studio plan is required')
            studio=MediaStudio(MediaProductionPipeline(self.media, CreativePlanner(self.catalyst.provider)), MediaQualityController())
            return asyncio.run(studio.render(payload_plan, provider=payload.get('provider'), concurrency=payload.get('concurrency',3), chain_references=bool(payload.get('chain_references',True)), max_retries=payload.get('max_retries',2))).as_dict()
        if kind=='media_batch':
            if not self.media: raise ValueError('Media engine is not configured')
            mode=payload.get('mode','image'); items=payload.get('items',[])[:16]
            async def _batch():
                limit = max(1, min(int(getattr(self.media.settings, 'max_parallel_agents', 4)), 8))
                semaphore = asyncio.Semaphore(limit)
                async def run_one(index, item):
                    async with semaphore:
                        if mode=='image':
                            result = await self.media.generate_image(item.get('prompt',''),item.get('provider'),item.get('references',[]),item.get('aspect_ratio','16:9'),item.get('quality','auto'),item.get('background','auto'),item.get('variants',1),item.get('negative_prompt',''),item.get('size'),item.get('output_compression'),item.get('options') or {})
                        else:
                            result = await self.media.generate_video(item.get('prompt',''),item.get('provider'),item.get('references',[]),item.get('aspect_ratio','16:9'),item.get('duration',8),item.get('resolution','720p'),item.get('audio',True),item.get('negative_prompt',''),item.get('fps'),item.get('seed'),item.get('options') or {})
                        return index, result
                return await asyncio.gather(*(run_one(i, item) for i, item in enumerate(items)), return_exceptions=True)
            results=asyncio.run(_batch())
            out=[]
            for i,r in enumerate(results): out.append({'index':i,'ok':not isinstance(r,Exception),'result':r if not isinstance(r,Exception) else str(r)})
            return {'mode':mode,'results':out}
        if kind=='research': return self.catalyst.research_engine.research(payload['query'],payload.get('limit',6),self.provenance)
        raise ValueError(f'Unsupported job kind: {kind}')
