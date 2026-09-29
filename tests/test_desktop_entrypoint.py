from html.parser import HTMLParser
from pathlib import Path


class DesktopDocument(HTMLParser):
    def __init__(self):
        super().__init__()
        self.classes = set()
        self.module_scripts = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.classes.update((attributes.get('class') or '').split())
        if tag == 'script' and attributes.get('type') == 'module':
            self.module_scripts.add(attributes.get('src'))


def test_desktop_vite_entrypoint_mounts_into_existing_shell():
    root = Path(__file__).resolve().parents[1]
    parser = DesktopDocument()
    parser.feed((root / 'desktop' / 'index.html').read_text(encoding='utf-8'))
    source = (root / 'desktop' / 'src' / 'main.js').read_text(encoding='utf-8')

    assert 'shell' in parser.classes
    assert '/src/main.js' in parser.module_scripts
    assert "document.querySelector('.shell')" in source
    assert "document.querySelector('#app')" not in source
    assert source.count('const root =') == 1