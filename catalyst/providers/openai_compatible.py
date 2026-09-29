import json,time
import httpx

class OpenAICompatibleProvider:
    """Small, provider-agnostic chat client with safe profile options."""
    _OPTION_KEYS = {
        "top_p", "min_p", "frequency_penalty", "presence_penalty", "seed",
        "reasoning_effort", "response_format", "parallel_tool_calls",
        "logprobs", "top_logprobs", "user", "extra_body",
    }

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120,
                 max_tokens: int = 4096, settings=None, options=None):
        self.settings=settings
        self.base_url=base_url.rstrip('/'); self.api_key=api_key; self.model=model; self.timeout=timeout; self.max_tokens=max_tokens
        self.options=dict(options or {})
    def _payload(self,messages,tools=None,temperature=.2,stream=False):
        payload={"model":self.model,"messages":messages,"temperature":temperature,"max_tokens":self.max_tokens,"stream":stream}
        request_options=self.options.get("chat", self.options)
        if isinstance(request_options, dict):
            payload.update({key: value for key, value in request_options.items()
                            if key in self._OPTION_KEYS and value is not None})
        if tools: payload["tools"]=tools; payload["tool_choice"]="auto"
        return payload
    def chat(self, messages, tools=None, temperature=0.2):
        if not self.api_key: raise RuntimeError('API key is not configured')
        if not self.model: raise RuntimeError('Model is not configured')
        payload=self._payload(messages,tools,temperature,False); last=None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response=client.post(f"{self.base_url}/chat/completions",headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"},json=payload); response.raise_for_status(); choice=response.json()['choices'][0]
                    return choice['message']
            except (httpx.HTTPError,KeyError,IndexError,ValueError) as e:
                last=e
                if attempt<2: time.sleep(0.5*(2**attempt))
        raise RuntimeError(f'Provider request failed: {last}')
    def stream(self,messages,tools=None,temperature=.2):
        if not self.api_key or not self.model: raise RuntimeError('Provider is not configured')
        payload=self._payload(messages,tools,temperature,True)
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream('POST',f"{self.base_url}/chat/completions",headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"},json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line: continue
                    if line.startswith('data: '): line=line[6:]
                    if line=='[DONE]': break
                    try:
                        obj=json.loads(line); delta=obj.get('choices',[{}])[0].get('delta',{})
                        if delta.get('content'): yield {'type':'content','text':delta['content']}
                        if delta.get('tool_calls'): yield {'type':'tool_calls','tool_calls':delta['tool_calls']}
                    except json.JSONDecodeError:
                        continue
