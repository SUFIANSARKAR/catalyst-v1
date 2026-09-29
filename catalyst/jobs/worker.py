import threading
import time
import uuid

class JobWorker:
    def __init__(self, jobs, handler, poll_seconds=2, automations=None):
        self.jobs = jobs; self.handler = handler; self.poll_seconds = max(1, int(poll_seconds)); self.automations = automations
        self._stop = threading.Event(); self.thread = None; self.worker_id = uuid.uuid4().hex[:12]

    def start(self):
        if self.thread and self.thread.is_alive(): return
        self._stop.clear(); self.thread = threading.Thread(target=self._run, name='catalyst-job-worker', daemon=True); self.thread.start()

    def stop(self):
        self._stop.set()
        if self.thread and self.thread is not threading.current_thread(): self.thread.join(timeout=max(1, self.poll_seconds + 1))

    def _dispatch_automations(self):
        if not self.automations: return
        for item in self.automations.claim_due(limit=4):
            try:
                self.jobs.create('goal', {'objective': item['objective'], 'automation_id': item['id']}, max_attempts=2)
                self.automations.mark_dispatched(item['id'], item['interval_minutes'])
            except Exception:
                self.automations.release_claim(item['id'])

    def _run(self):
        while not self._stop.is_set():
            try:
                self._dispatch_automations()
                worked = False
                for _ in range(4):
                    job = self.jobs.claim_next(self.worker_id)
                    if not job: break
                    worked = True
                    jid = job['id']
                    try:
                        result = self.handler(job)
                        self.jobs.finish(jid, 'completed', result=result)
                    except Exception as exc:
                        self.jobs.fail_or_retry(jid, str(exc), backoff_seconds=10)
                self._stop.wait(0.25 if worked else self.poll_seconds)
            except Exception:
                time.sleep(min(self.poll_seconds, 5))
