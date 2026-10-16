import sys,json
if sys.argv[1]=='search':
    from ddgs import DDGS
    result=DDGS(timeout=20).text(sys.argv[2],max_results=5)
else:
    import requests
    from bs4 import BeautifulSoup
    url=sys.argv[2]
    if not url.startswith(('https://','http://')): raise ValueError('HTTP(S) URL required')
    with requests.get(url,timeout=25,stream=True,headers={'User-Agent':'LocalAIStudio/0.1'}) as r:
        r.raise_for_status(); parts=[]; size=0
        for chunk in r.iter_content(16384):
            size+=len(chunk)
            if size>2_000_000: raise ValueError('Page exceeds 2 MB')
            parts.append(chunk)
    soup=BeautifulSoup(b''.join(parts),'html.parser')
    for t in soup(['script','style','nav','footer']): t.decompose()
    result={'url':r.url,'title':soup.title.get_text(' ',strip=True) if soup.title else '', 'text':soup.get_text(' ',strip=True)[:24000]}
print(json.dumps(result,ensure_ascii=False))
