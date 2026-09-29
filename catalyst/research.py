import re, socket, ipaddress, time
from urllib.parse import urlencode
import httpx
from pathlib import Path

class ResearchEngine:
    """Bounded web research with source capture; search uses DuckDuckGo HTML without extra packages."""
    def __init__(self,data_root:str):self.root=Path(data_root)/'research';self.root.mkdir(parents=True,exist_ok=True)
    def _public(self,url):
        from urllib.parse import urlparse
        u=urlparse(url)
        if u.scheme not in {'http','https'} or not u.hostname:raise ValueError('Only public http(s) URLs are allowed')
        for item in socket.getaddrinfo(u.hostname,None):
            a=ipaddress.ip_address(item[4][0])
            if any((a.is_private,a.is_loopback,a.is_link_local,a.is_reserved,a.is_multicast)):raise PermissionError('Blocked private/loopback network target')

    def _get_public(self,url,max_redirects=5):
        current=url
        for _ in range(max_redirects+1):
            self._public(current)
            r=httpx.get(current,headers={'User-Agent':'Catalyst/1.0'},timeout=30,follow_redirects=False)
            if r.status_code in {301,302,303,307,308}:
                location=r.headers.get('location')
                if not location: return r
                from urllib.parse import urljoin
                current=urljoin(current,location)
                continue
            return r
        raise ValueError('Too many redirects')

    def search(self,query,limit=8):
        url='https://html.duckduckgo.com/html/?'+urlencode({'q':query})
        self._public(url)
        r=self._get_public(url);r.raise_for_status();html=r.text
        out=[]
        for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',html,re.I|re.S):
            href=re.sub(r'&amp;','&',m.group(1));title=re.sub(r'<.*?>','',m.group(2)).strip()
            out.append({'title':title,'url':href})
            if len(out)>=max(1,min(limit,20)):break
        return out
    def fetch(self,url):
        r=self._get_public(url);r.raise_for_status();
        text=re.sub(r'<script.*?</script>|<style.*?</style>',' ',r.text,flags=re.I|re.S);text=re.sub(r'<[^>]+>',' ',text);text=re.sub(r'\s+',' ',text).strip()
        return {'url':str(r.url),'status':r.status_code,'content':text[:300000]}
    def research(self,query,limit=5,provenance=None):
        results=self.search(query,limit);sources=[]
        for item in results:
            try:sources.append(self.fetch(item['url'])|{'title':item['title']})
            except Exception as e:sources.append(item|{'error':str(e)})
            time.sleep(0.1)
        stamp=str(int(time.time()));path=self.root/f'{stamp}.md';lines=[f'# Catalyst Research — {query}','']
        for i,s in enumerate(sources,1):lines += [f'## [{i}] {s.get("title", "Source")}',s['url']]
        path.write_text('\n'.join(lines),encoding='utf-8')
        if provenance:
            for item in sources: provenance.add('web_source',item.get('url',''),item.get('title',''),{'query':query,'artifact':str(path)})
        return {'query':query,'sources':sources,'artifact':str(path)}
