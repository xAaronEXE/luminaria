"""In-process web retrieval with one result shape and distinct failure categories.

Every result is an envelope: status ok | empty | error, an error category when
relevant, the source, retrieval time, attempts and duration. Fetched page text
is untrusted data and never instructions.
"""
import asyncio, io, ipaddress, re, time
from urllib.parse import urlsplit
import httpx

CATEGORIES = ('invalid_input', 'not_found', 'auth', 'blocked', 'throttled', 'timeout', 'network', 'server',
              'unsupported', 'too_large', 'extraction', 'needs_javascript', 'unavailable', 'cancelled')
TEXT_LIMIT = 24000
HTML_LIMIT = 5_000_000
PDF_LIMIT = 20_000_000
CACHE_SECONDS = 600
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36 Luminaria',
           'Accept': 'text/html,application/xhtml+xml,application/pdf;q=0.9,text/plain;q=0.8,*/*;q=0.5', 'Accept-Language': 'en;q=0.9,*;q=0.5'}
GUIDANCE = {
    'invalid_input': 'Check the address. Only http and https links can be fetched.',
    'not_found': 'The page does not exist at this address. Search for its current location instead of retrying.',
    'auth': 'This page needs a sign-in. Use a connected browser session if the user has one; do not try to bypass it.',
    'blocked': 'The site refused automated access. Do not retry; use another source or a connected browser if appropriate.',
    'throttled': 'The site is rate-limiting requests. Wait before trying again or use another source.',
    'timeout': 'The site did not respond in time. Try once more later or use another source.',
    'network': 'The site could not be reached. Check the address or try another source.',
    'server': 'The site had an internal error. Try another source.',
    'unsupported': 'This file type cannot be read as text here.',
    'too_large': 'The response is too large to read in full. Look for a smaller page or a specific section.',
    'extraction': 'The page loaded but no readable text could be extracted.',
    'needs_javascript': 'The page builds its content with JavaScript. A connected browser tool can read it.',
    'unavailable': 'Web search is not available in this installation.',
}
_cache = {}

def envelope(status, source='', started=None, attempts=1, category=None, **fields):
    out = {'status': status, 'source': source, 'retrieved_at': round(time.time(), 3), 'attempts': attempts,
           'duration_ms': int((time.monotonic() - started) * 1000) if started else 0}
    if category:
        out['category'] = category
        out.setdefault('guidance', GUIDANCE.get(category, ''))
    out.update({k: v for k, v in fields.items() if v is not None})
    return out

def failure(category, message, source='', started=None, attempts=1, **fields):
    return envelope('error', source, started, attempts, category, message=message, **fields)

def check_url(url):
    if not isinstance(url, str) or len(url) > 4000: raise ValueError('invalid_input')
    parts = urlsplit(url.strip())
    if parts.scheme not in ('http', 'https') or not parts.hostname: raise ValueError('invalid_input')
    host = parts.hostname
    try:
        address = ipaddress.ip_address(host)
        if address.is_loopback or address.is_link_local or address.is_unspecified: raise ValueError('invalid_input')
    except ValueError as error:
        if str(error) == 'invalid_input': raise
    if host in ('localhost',) or host.endswith('.localhost'): raise ValueError('invalid_input')
    return url.strip()

NOISE = re.compile(r'(^|[-_ ])(nav|navbar|menu|footer|header|sidebar|cookie|consent|banner|advert|ads?|promo|share|social|related|newsletter|subscribe|breadcrumb|comments?|popup|modal)([-_ ]|$)', re.I)

def extract_html(raw, charset=None):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw, 'html.parser', from_encoding=charset)
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    scripts = len(soup.find_all('script'))
    for tag in soup(['script', 'style', 'noscript', 'svg', 'iframe', 'form', 'button', 'template', 'nav', 'footer', 'aside']): tag.decompose()
    for tag in soup.find_all(attrs={'role': re.compile('navigation|banner|contentinfo|complementary|dialog', re.I)}): tag.decompose()
    for tag in soup.find_all(True):
        if getattr(tag, 'decomposed', False): continue
        attrs = getattr(tag, 'attrs', None)
        if not attrs: continue
        label = ' '.join(attrs.get('class', []) or []) + ' ' + str(attrs.get('id', ''))
        if tag.name not in ('body', 'html', 'main', 'article') and NOISE.search(label): tag.decompose()
    root = soup.find('article') or soup.find('main') or soup.find(attrs={'role': 'main'})
    if root is None or len(root.get_text(' ', strip=True)) < 200:
        candidates = soup.find_all(['div', 'section', 'td']) or [soup.body or soup]
        root = max(candidates, key=lambda el: len(' '.join(p.get_text(' ', strip=True) for p in el.find_all('p', recursive=True))) or 0, default=soup)
        if len(root.get_text(' ', strip=True)) < 200: root = soup.body or soup
    lines = []
    for el in root.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li', 'pre', 'blockquote', 'td', 'th', 'dt', 'dd']):
        if el.find_parent(['li', 'pre', 'blockquote', 'td', 'th']) and el.name in ('p', 'li'): continue
        text = el.get_text(' ', strip=True) if el.name != 'pre' else el.get_text('\n', strip=False).strip()
        if not text: continue
        if el.name in ('h1', 'h2', 'h3', 'h4'): text = '#' * int(el.name[1]) + ' ' + text
        elif el.name == 'li': text = '- ' + text
        lines.append(text)
    body = '\n\n'.join(dict.fromkeys(lines)) if lines else root.get_text(' ', strip=True)
    return title, re.sub(r'[ \t]+', ' ', body).strip(), scripts

def extract_pdf(raw):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted:
        try: reader.decrypt('')
        except Exception: raise ValueError('auth')
    pages = []
    for page in reader.pages[:200]:
        pages.append((page.extract_text() or '').strip())
        if sum(len(p) for p in pages) > TEXT_LIMIT * 2: break
    title = str((reader.metadata or {}).get('/Title', '') or '')
    return title, '\n\n'.join(p for p in pages if p), len(reader.pages)

def classify_status(code):
    if code in (401, 407): return 'auth'
    if code in (403, 451): return 'blocked'
    if code in (404, 410): return 'not_found'
    if code == 429: return 'throttled'
    if code >= 500: return 'server'
    return 'blocked' if code >= 400 else None

async def fetch(url, refresh=False, client=None, sleep=asyncio.sleep):
    started = time.monotonic()
    try: url = check_url(url)
    except ValueError: return failure('invalid_input', 'Not a fetchable public http(s) address.', str(url)[:300], started)
    cached = _cache.get(url)
    if cached and not refresh and time.time() - cached['retrieved_at'] < CACHE_SECONDS:
        return {**cached, 'cached': True, 'age_seconds': int(time.time() - cached['retrieved_at'])}
    own = client is None
    client = client or httpx.AsyncClient(timeout=httpx.Timeout(20, connect=8), follow_redirects=True, max_redirects=6, headers=HEADERS, trust_env=False)
    attempts = 0
    try:
        while True:
            attempts += 1
            try:
                result = await _fetch_once(client, url, started, attempts)
            except (httpx.TimeoutException,) as error:
                result = failure('timeout', 'The site did not respond within 20 seconds.', url, started, attempts)
            except httpx.TooManyRedirects:
                return failure('network', 'The page redirected too many times.', url, started, attempts)
            except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError) as error:
                result = failure('network', 'Could not connect: ' + (str(error) or type(error).__name__)[:200], url, started, attempts)
            category = result.get('category')
            retry_after = result.pop('_retry_after', None)
            if category in ('timeout', 'network', 'server', 'throttled') and attempts < (2 if category == 'throttled' else 3):
                wait = min(retry_after if retry_after is not None else attempts, 8)
                if category == 'throttled' and retry_after is not None and retry_after > 8: return result
                await sleep(wait); continue
            if result['status'] == 'ok': _cache[url] = result
            if len(_cache) > 64: _cache.pop(next(iter(_cache)))
            return result
    except asyncio.CancelledError:
        raise
    finally:
        if own: await client.aclose()

async def _fetch_once(client, url, started, attempts):
    async with client.stream('GET', url) as response:
        final = str(response.url)
        category = classify_status(response.status_code)
        if category:
            retry = response.headers.get('retry-after', '')
            return failure(category, f'The site answered {response.status_code}.', final, started, attempts, http_status=response.status_code,
                           _retry_after=int(retry) if retry.isdigit() else None)
        kind = response.headers.get('content-type', '').split(';')[0].strip().lower()
        pdf = kind == 'application/pdf' or (not kind and final.lower().endswith('.pdf'))
        textual = kind in ('', 'text/html', 'application/xhtml+xml') or kind.startswith('text/') or kind in ('application/json', 'application/xml', 'application/rss+xml', 'application/atom+xml')
        if not pdf and not textual:
            return failure('unsupported', f'This is a {kind or "binary"} file, not a page that can be read as text.', final, started, attempts, content_type=kind)
        limit = PDF_LIMIT if pdf else HTML_LIMIT
        declared = response.headers.get('content-length', '')
        if declared.isdigit() and int(declared) > limit:
            return failure('too_large', f'The response is {int(declared) // 1_000_000} MB; the limit is {limit // 1_000_000} MB.', final, started, attempts, content_type=kind)
        chunks, size = [], 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > limit: return failure('too_large', f'The response passed the {limit // 1_000_000} MB limit.', final, started, attempts, content_type=kind)
            chunks.append(chunk)
        raw = b''.join(chunks)
        charset = response.charset_encoding
    try:
        if pdf:
            title, text, pages = extract_pdf(raw); extra = {'pages': pages}
            if not text: return failure('extraction', 'The PDF has no extractable text (it may be scanned images).', final, started, attempts, content_type='application/pdf', pages=pages)
        elif kind in ('', 'text/html', 'application/xhtml+xml') or raw[:200].lstrip().lower().startswith((b'<!doctype html', b'<html')):
            title, text, scripts = extract_html(raw, charset); extra = {}
            if len(text) < 200 and scripts >= 5:
                return failure('needs_javascript', 'The page returned almost no text without running scripts.', final, started, attempts, content_type=kind or 'text/html', title=title or None)
        else:
            title, extra = '', {}
            text = raw.decode(charset or 'utf-8', 'replace')
    except ValueError as error:
        if str(error) == 'auth': return failure('auth', 'The PDF is password protected.', final, started, attempts, content_type='application/pdf')
        return failure('extraction', 'The content could not be parsed: ' + str(error)[:200], final, started, attempts, content_type=kind)
    except Exception as error:
        return failure('extraction', 'The content could not be parsed: ' + type(error).__name__, final, started, attempts, content_type=kind)
    text = text.strip()
    if not text: return envelope('empty', final, started, attempts, content_type=kind or 'text/html', title=title or None, message='The page loaded but has no readable text.')
    return envelope('ok', final, started, attempts, content_type='application/pdf' if pdf else (kind or 'text/html'), title=title or None,
                    text=text[:TEXT_LIMIT], truncated=len(text) > TEXT_LIMIT, total_characters=len(text), redirected=final != url or None, **extra)

async def search(query, engine=None):
    started = time.monotonic()
    query = (query or '').strip()
    if not query or len(query) > 500: return failure('invalid_input', 'Provide a search query of up to 500 characters.', '', started)
    def run():
        if engine: return engine(query)
        from ddgs import DDGS
        return DDGS(timeout=15).text(query, max_results=6)
    attempts = 0
    while True:
        attempts += 1
        try:
            rows = await asyncio.wait_for(asyncio.to_thread(run), 25)
            break
        except ImportError:
            return failure('unavailable', 'The web search component is missing from this installation.', 'web search', started, attempts)
        except asyncio.TimeoutError:
            if attempts < 2: continue
            return failure('timeout', 'Web search did not respond in time.', 'web search', started, attempts)
        except Exception as error:
            text = str(error).lower()
            category = 'throttled' if 'ratelimit' in text or '429' in text or 'rate limit' in text else 'empty' if 'no results' in text else 'network'
            if category == 'empty': rows = []; break
            if attempts < 2 and category == 'network': continue
            return failure(category, 'Web search failed: ' + str(error)[:200], 'web search', started, attempts)
    results = [{'title': r.get('title', ''), 'url': r.get('href') or r.get('url', ''), 'snippet': r.get('body', '')[:500]} for r in rows or [] if isinstance(r, dict)]
    if not results: return envelope('empty', 'web search', started, attempts, message='No results. Try different or fewer words; this does not mean the information does not exist.')
    return envelope('ok', 'web search', started, attempts, results=results)
