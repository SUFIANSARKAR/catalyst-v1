from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from catalyst.version import __version__

DEFAULT_OUT = ROOT.parent / f"Catalyst-Master-v{__version__}-Apex-Intelligence-Complete.zip"

EXCLUDED_PARTS = {
    ".git", ".idea", ".vscode", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules", ".venv", "venv", "dist", "build",
}
EXCLUDED_FILES = {"secrets.json", ".env", ".env.local", ".env.production", ".env.development", "RELEASE_SOURCE_MANIFEST.txt"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def include(path: pathlib.Path) -> bool:
    rel = path.relative_to(ROOT)
    parts = rel.parts
    if any(part in EXCLUDED_PARTS for part in parts):
        return False
    if rel.name in EXCLUDED_FILES or any(rel.name.startswith(prefix) for prefix in (".env.",)):
        return False
    if rel.suffix in EXCLUDED_SUFFIXES:
        return False
    if rel.name.startswith("ui-preview"):
        return False
    if parts and parts[0] == "catalyst_data" and rel.as_posix() != "catalyst_data/README.md":
        return False
    # Generated proposal/evidence state is runtime, not source.
    if parts and parts[0] in {"proposals", "evidence", "runtime", "tmp"}:
        return False
    # Keep only source assets from the deployment frontends; generated bundles are excluded.
    if "node_modules" in parts:
        return False
    return True


def build(output: pathlib.Path) -> tuple[pathlib.Path, str, int]:
    output.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and include(p))
    # Store a source manifest in-memory and include it as a deterministic archive member.
    manifest_lines=[]
    for p in files:
        data=p.read_bytes()
        manifest_lines.append(f"{hashlib.sha256(data).hexdigest()}  {p.relative_to(ROOT).as_posix()}  {len(data)}")
    manifest=(f"Catalyst release {__version__}\
"+"\
".join(manifest_lines)+"\
").encode()

    forbidden_files=[p for p in ROOT.rglob("*") if p.is_file() and not include(p) and p.relative_to(ROOT).as_posix()=="catalyst_data/secrets.json"]
    if not forbidden_files:
        # The builder does not require runtime state to exist; its absence is normal.
        pass

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in files:
            rel=p.relative_to(ROOT).as_posix()
            info=zipfile.ZipInfo(rel)
            info.date_time=(1980,1,1,0,0,0)
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            zf.writestr(info, p.read_bytes())
        info=zipfile.ZipInfo("RELEASE_SOURCE_MANIFEST.txt")
        info.date_time=(1980,1,1,0,0,0)
        info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o100644 << 16
        zf.writestr(info, manifest)
        zf.comment=f"Catalyst {__version__} release archive".encode()

    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    return output, digest, len(files)+1


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUT)
    args=parser.parse_args()
    out,digest,count=build(args.output)
    print(f"PASS: packaged {count} files")
    print(f"ARCHIVE: {out}")
    print(f"SHA256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
