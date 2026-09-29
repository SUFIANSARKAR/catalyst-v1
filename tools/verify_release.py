from __future__ import annotations

import ast
import importlib
import pathlib
import zipfile
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(archive: pathlib.Path | None = None) -> int:
    py_files = list((ROOT / 'catalyst').rglob('*.py')) + list((ROOT / 'tests').rglob('*.py'))
    if not py_files:
        print('FAIL: no Python files found')
        return 2
    for path in py_files:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    print(f'PASS: AST parsed {len(py_files)} Python files')
    result = subprocess.run([sys.executable, '-m', 'compileall', '-q', str(ROOT / 'catalyst'), str(ROOT / 'tests')], cwd=ROOT)
    if result.returncode:
        return result.returncode
    print('PASS: bytecode compilation')
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q'], cwd=ROOT)
    if result.returncode:
        return result.returncode
    print('PASS: test suite')
    from catalyst.version import __version__
    expected = __version__
    if str(expected) != '5.7.0':
        print(f'FAIL: unexpected release version {expected}')
        return 3
    if archive is not None:
        if not archive.exists():
            print(f'FAIL: archive not found: {archive}')
            return 4
        forbidden = []
        with zipfile.ZipFile(archive) as zf:
            bad_prefixes = ('catalyst_data/')
            bad_names = {'secrets.json'}
            for name in zf.namelist():
                norm = name.replace('\\', '/')
                parts = pathlib.PurePosixPath(norm).parts
                if any(part in {'__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','node_modules','.venv','venv'} for part in parts):
                    forbidden.append(name)
                if norm.endswith('.pyc') or norm.endswith('.db') or norm.endswith('.db-wal') or norm.endswith('.db-shm'):
                    forbidden.append(name)
                if pathlib.PurePosixPath(norm).name in bad_names or norm.startswith(bad_prefixes) and pathlib.PurePosixPath(norm).name != 'README.md':
                    forbidden.append(name)
        if forbidden:
            print('FAIL: forbidden runtime material in archive:')
            for name in forbidden[:30]: print(f'  {name}')
            return 5
        print('PASS: archive hygiene')
    print(f'PASS: source files verified for Catalyst {expected}')
    return 0


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive', type=pathlib.Path)
    args=parser.parse_args()
    raise SystemExit(main(args.archive))
