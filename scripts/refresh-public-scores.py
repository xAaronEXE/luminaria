"""Refresh the bundled public score snapshot from Epoch AI's ECI dataset."""
import argparse
import csv
import io
import json
import math
from pathlib import Path
from urllib.request import urlopen

SOURCE = 'https://epoch.ai/data/eci_scores.csv'
TARGET = Path(__file__).resolve().parents[1] / 'catalog' / 'epoch-eci.json'


def parse_scores(text):
    scores = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            score, low, high = (float(row[key]) for key in ('eci', 'eci_ci_low', 'eci_ci_high'))
        except (KeyError, ValueError, TypeError):
            continue
        name = row.get('Display name') or row.get('Model')
        if name and all(map(math.isfinite, (score, low, high))) and low <= score <= high:
            scores.append({'name': name, 'eci': score, 'low': low, 'high': high})
    if not scores:
        raise ValueError('Epoch AI returned no usable ECI scores.')
    return {'source': SOURCE, 'license': 'CC BY 4.0', 'scores': scores}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-file', type=Path)
    args = parser.parse_args()
    if args.source_file:
        raw = args.source_file.read_bytes()
    else:
        with urlopen(SOURCE, timeout=30) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Epoch AI score data exceeded the expected size.')
    data = parse_scores(raw.decode('utf-8-sig'))
    pending = TARGET.with_suffix('.tmp')
    pending.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    pending.replace(TARGET)


if __name__ == '__main__':
    main()
