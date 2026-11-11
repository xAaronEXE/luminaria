"""Look up exact public ECI matches. Local evaluation scores use a separate scale."""
import json
import re
from functools import lru_cache

from .config import ROOT


def model_key(name):
    return re.sub(r'[^a-z0-9]', '', name.casefold())


@lru_cache(maxsize=1)
def catalog():
    path = ROOT / 'catalog' / 'epoch-eci.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    matched, duplicates = {}, set()
    for score in data['scores']:
        key = model_key(score['name'])
        if key in matched:
            duplicates.add(key)
        matched[key] = score
    return {key: score for key, score in matched.items() if key not in duplicates}


def public_score(entry):
    if entry.get('variant') != 'standard':
        return None
    return catalog().get(model_key(entry['name']))
