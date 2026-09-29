from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import re
from typing import Any

DEFAULT_IGNORES = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'dist', 'build', '.next'}
LANG = {'.py':'python','.js':'javascript','.jsx':'javascript','.ts':'typescript','.tsx':'typescript','.rs':'rust','.go':'go','.java':'java','.cpp':'cpp','.c':'c','.h':'c','.hpp':'cpp','.cs':'csharp','.kt':'kotlin','.swift':'swift','.md':'markdown','.json':'json','.yaml':'yaml','.yml':'yaml','.toml':'toml'}

@dataclass(frozen=True)
class FileRecord:
    path: str
    language: str
    bytes: int
    lines: int
    is_test: bool

@dataclass(frozen=True)
class SymbolRecord:
    path: str
    name: str
    kind: str
    line: int

class CodebaseIntelligence:
    """Fast repository reconnaissance for Catalyst's engineering brain.

    It deliberately uses deterministic parsing first. Optional richer AST/LSP
    integrations can be layered on later without changing the repository model.
    """
    def __init__(self, root: str, max_files: int = 20000):
        self.root = Path(root).resolve()
        self.max_files = max(100, int(max_files))

    def _iter_files(self):
        count = 0
        for p in self.root.rglob('*'):
            if count >= self.max_files: break
            if not p.is_file(): continue
            if any(part in DEFAULT_IGNORES for part in p.parts): continue
            try:
                rel = p.relative_to(self.root)
            except ValueError:
                continue
            count += 1
            yield p, rel

    def inventory(self) -> list[FileRecord]:
        out=[]
        for p, rel in self._iter_files():
            lang=LANG.get(p.suffix.lower(), 'other')
            try:
                text=p.read_text(encoding='utf-8', errors='ignore')
                lines=text.count('\n') + (1 if text else 0)
            except OSError:
                lines=0
            out.append(FileRecord(str(rel), lang, p.stat().st_size, lines, bool(re.search(r'(^|/)(test_|tests?/|.*_test\.|.*\.spec\.)', str(rel), re.I))))
        return out

    def symbols(self, limit: int = 5000) -> list[SymbolRecord]:
        out=[]
        patterns={
            'python': [(r'^\s*class\s+(\w+)', 'class'), (r'^\s*(?:async\s+)?def\s+(\w+)', 'function')],
            'javascript': [(r'^\s*(?:export\s+)?class\s+(\w+)', 'class'), (r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)', 'function')],
            'typescript': [(r'^\s*(?:export\s+)?class\s+(\w+)', 'class'), (r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)', 'function')],
            'rust': [(r'^\s*(?:pub\s+)?struct\s+(\w+)', 'struct'), (r'^\s*(?:pub\s+)?fn\s+(\w+)', 'function')],
            'go': [(r'^\s*type\s+(\w+)\s+struct', 'struct'), (r'^\s*func\s+(\w+)', 'function')],
        }
        for rec in self.inventory():
            if rec.language not in patterns: continue
            p=self.root / rec.path
            try: lines=p.read_text(encoding='utf-8',errors='ignore').splitlines()
            except OSError: continue
            for i,line in enumerate(lines,1):
                for pat,kind in patterns[rec.language]:
                    m=re.search(pat,line)
                    if m:
                        out.append(SymbolRecord(rec.path,m.group(1),kind,i))
                        if len(out)>=limit:return out
        return out

    def repo_map(self) -> dict[str, Any]:
        files=self.inventory(); symbols=self.symbols()
        by_lang={}
        for f in files: by_lang[f.language]=by_lang.get(f.language,0)+1
        tests=sum(f.is_test for f in files)
        return {
            'root':str(self.root), 'files':len(files), 'tests':tests,
            'languages':dict(sorted(by_lang.items(), key=lambda x:(-x[1],x[0]))),
            'total_bytes':sum(f.bytes for f in files), 'total_lines':sum(f.lines for f in files),
            'symbols':[asdict(s) for s in symbols[:2000]],
            'top_files':[asdict(f) for f in sorted(files,key=lambda x:x.bytes,reverse=True)[:50]],
        }

    def read(self, relative_path: str, max_chars: int = 120000) -> str:
        p=(self.root / relative_path).resolve()
        if p != self.root and self.root not in p.parents: raise PermissionError('Path escapes codebase root')
        return p.read_text(encoding='utf-8',errors='ignore')[:max_chars]
