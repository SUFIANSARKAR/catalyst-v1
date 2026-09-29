from __future__ import annotations
import asyncio, json, os, shlex
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]

class MCPGatewayError(RuntimeError): pass

class _StdioSession:
    def __init__(self, argv: list[str], env: dict[str,str], timeout: float):
        self.argv=argv; self.env=env; self.timeout=timeout
        self.proc=None; self.lock=asyncio.Lock(); self.next_id=0

    async def start(self):
        if self.proc and self.proc.returncode is None: return
        env={'PATH':os.environ.get('PATH','')}; env.update(self.env)
        self.proc=await asyncio.create_subprocess_exec(*self.argv,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env=env)

    async def request(self, method:str, params:dict[str,Any]|None=None):
        async with self.lock:
            await self.start()
            self.next_id += 1; rid=self.next_id
            payload={'jsonrpc':'2.0','id':rid,'method':method,'params':params or {}}
            self.proc.stdin.write((json.dumps(payload,separators=(',',':'))+'\n').encode()); await self.proc.stdin.drain()
            async def wait_response():
                while True:
                    line=await self.proc.stdout.readline()
                    if not line: raise MCPGatewayError('MCP server closed stdout before response')
                    try: msg=json.loads(line.decode())
                    except json.JSONDecodeError: continue
                    if msg.get('id') != rid: continue
                    if 'error' in msg: raise MCPGatewayError(str(msg['error']))
                    return msg.get('result')
            return await asyncio.wait_for(wait_response(),timeout=self.timeout)

    async def notify(self, method:str, params:dict[str,Any]|None=None):
        await self.start()
        self.proc.stdin.write((json.dumps({'jsonrpc':'2.0','method':method,'params':params or {}},separators=(',',':'))+'\n').encode()); await self.proc.stdin.drain()

    async def close(self):
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try: await asyncio.wait_for(self.proc.wait(),2)
            except asyncio.TimeoutError: self.proc.kill()

class MCPGateway:
    """Catalyst-owned MCP gateway with persistent stdio sessions and policy boundaries."""
    def __init__(self, *, allowed_servers: set[str] | None = None,
                 allowed_tools: set[str] | None = None, timeout: float = 30.0):
        self.allowed_servers=allowed_servers or set(); self.allowed_tools=allowed_tools or set(); self.timeout=max(1.0,float(timeout))
        self._servers:dict[str,dict[str,Any]]={}; self._sessions:dict[str,_StdioSession]={}

    def register_stdio(self,name:str,command:str,env:dict[str,str]|None=None)->None:
        if not name or (self.allowed_servers and name not in self.allowed_servers): raise PermissionError(f'MCP server not allowed: {name}')
        parts=shlex.split(command)
        if not parts: raise ValueError('MCP command is empty')
        safe_env={str(k):str(v) for k,v in (env or {}).items() if str(k).isidentifier()}
        self._servers[name]={'kind':'stdio','argv':parts,'env':safe_env}
        self._sessions[name]=_StdioSession(parts,safe_env,self.timeout)

    def _allowed_tool(self,name:str)->bool: return not self.allowed_tools or name in self.allowed_tools

    async def initialize(self,server_name:str)->dict[str,Any]:
        session=self._sessions.get(server_name)
        if not session: raise KeyError(server_name)
        result=await session.request('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'catalyst-mcp-gateway','version':'3.17.0'}})
        await session.notify('notifications/initialized',{})
        return result or {}

    async def list_tools(self,server_name:str)->list[MCPTool]:
        session=self._sessions.get(server_name)
        if not session: raise KeyError(server_name)
        result=await session.request('tools/list',{})
        return [MCPTool(str(x['name']),str(x.get('description','')),x.get('inputSchema') or {}) for x in (result or {}).get('tools',[]) if x.get('name') and self._allowed_tool(str(x['name']))]

    async def call_tool(self,server_name:str,tool_name:str,arguments:dict[str,Any]|None=None)->dict[str,Any]:
        if not self._allowed_tool(tool_name): raise PermissionError(f'MCP tool not allowed: {tool_name}')
        session=self._sessions.get(server_name)
        if not session: raise KeyError(server_name)
        return await session.request('tools/call',{'name':tool_name,'arguments':arguments or {}})

    async def close(self):
        await asyncio.gather(*(s.close() for s in self._sessions.values()),return_exceptions=True)
