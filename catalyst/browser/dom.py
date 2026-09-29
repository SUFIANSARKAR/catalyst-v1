from __future__ import annotations
import re
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class InteractiveElement:
    index: int
    tag: str
    role: str
    text: str
    aria_label: str
    placeholder: str
    href: str
    selector: str
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

class DOMPerception:
    """Compact live-page perception for Catalyst's browser layer.

    This deliberately extracts perception only; it never executes a browser action.
    Execution remains owned by Catalyst Mission Control.
    """
    JS = r"""
    () => {
      const visible = (e) => {
        const s = getComputedStyle(e), r = e.getBoundingClientRect();
        return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity || 1) > 0
          && r.width > 0 && r.height > 0;
      };
      const interactive = (e) => {
        const tag = e.tagName.toLowerCase();
        const role = (e.getAttribute('role') || '').toLowerCase();
        return ['a','button','input','textarea','select','option','summary'].includes(tag)
          || ['button','link','checkbox','combobox','menuitem','radio','switch','tab','textbox'].includes(role)
          || e.hasAttribute('contenteditable') || e.hasAttribute('onclick');
      };
      const clean = (s, n=160) => (s || '').replace(/\\s+/g,' ').trim().slice(0,n);
      const nodes = [...document.querySelectorAll('a,button,input,textarea,select,option,summary,[role],[contenteditable],[onclick]')]
        .filter(e => visible(e) && interactive(e));
      return nodes.slice(0, 500).map((e, i) => {
        const r=e.getBoundingClientRect();
        const label=e.getAttribute('aria-label') || e.getAttribute('title') || '';
        const text=clean(e.innerText || e.value || e.textContent || '');
        const href=e.href || '';
        const id=e.id ? '#' + CSS.escape(e.id) : '';
        const name=e.getAttribute('name');
        const selector=id || (name ? `${e.tagName.toLowerCase()}[name="${CSS.escape(name)}"]` : `${e.tagName.toLowerCase()}`);
        return {tag:e.tagName.toLowerCase(), role:e.getAttribute('role') || '', text, aria_label:clean(label,120),
          placeholder:clean(e.getAttribute('placeholder') || '',120), href, selector,
          x:r.x,y:r.y,width:r.width,height:r.height};
      });
    }
    """

    async def extract(self, page, *, max_elements: int = 250) -> dict[str, Any]:
        raw = await page.evaluate(self.JS)
        elements: list[InteractiveElement] = []
        for i, item in enumerate(raw[:max(1, min(int(max_elements), 500))], 1):
            elements.append(InteractiveElement(index=i, **item))
        title = await page.title()
        url = page.url
        text = ''
        try:
            text = (await page.locator('body').inner_text(timeout=2000))[:12000]
        except Exception:
            pass
        return {
            'url': url,
            'title': title[:300],
            'text': re.sub(r'\s+', ' ', text).strip(),
            'interactive_count': len(elements),
            'elements': [e.as_dict() for e in elements],
        }
