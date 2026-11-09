"""Validate a small product CSV without changing the original. Python 3.11+."""
from __future__ import annotations
import argparse
import csv
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = ['id', 'name', 'price_rub', 'category']


def safe_cell(value: str) -> str:
    """Keep formula-like text inert when opening the output in a spreadsheet."""
    value = ' '.join(value.split())
    return "'" + value if value.startswith(('=', '+', '-', '@')) else value


def price(value: str) -> str:
    value = value.strip().replace('\u00a0', '').replace(' ', '').replace(',', '.')
    if not re.fullmatch(r'\d+(?:\.\d{1,2})?', value):
        raise ValueError('price_rub must be a non-negative amount with up to 2 decimal places')
    try:
        n = Decimal(value)
    except InvalidOperation as error:
        raise ValueError('invalid price_rub') from error
    return format(n, '.2f')


def validate(source: Path) -> tuple[list[dict], list[dict], dict]:
    with source.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle, delimiter=';')
        if reader.fieldnames != FIELDS:
            raise ValueError('Expected headers in this order: ' + ';'.join(FIELDS))
        rows = list(reader)
    ids = Counter((r.get('id') or '').strip() for r in rows)
    clean, rejected = [], []
    for number, raw in enumerate(rows, start=2):
        problems = []
        row = {k: ' '.join((raw.get(k) or '').split()) for k in FIELDS}
        if None in raw or any(raw.get(k) is None for k in FIELDS):
            problems.append('wrong number of columns')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', row['id']):
            problems.append('id must contain 1-64 Latin letters, digits, underscores or hyphens')
        if ids[(raw.get('id') or '').strip()] > 1:
            problems.append('duplicate id: every occurrence rejected')
        for key in ['name', 'category']:
            if not row[key]:
                problems.append(key + ' is required')
        try:
            row['price_rub'] = price(row['price_rub'])
        except ValueError as error:
            problems.append(str(error))
        if problems:
            rejected.append({'line': number, 'raw_json': json.dumps(raw, ensure_ascii=False),
                             'errors': ' | '.join(problems)})
        else:
            clean.append({k: safe_cell(v) for k, v in row.items()})
    return clean, rejected, {'read': len(rows), 'accepted': len(clean), 'rejected': len(rejected)}


def run(source: Path, destination: Path) -> dict:
    clean, rejected, report = validate(source)
    # An existing output is never overwritten. Input remains untouched.
    destination.mkdir(parents=True, exist_ok=False)
    for filename, rows, fields in [('clean.csv', clean, FIELDS),
                                   ('rejected.csv', rejected, ['line', 'raw_json', 'errors'])]:
        with (destination / filename).open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter=';')
            writer.writeheader()
            writer.writerows(rows)
    (destination / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    args = parser.parse_args()
    try:
        result = run(args.source, args.output)
    except (ValueError, OSError, UnicodeError, csv.Error) as error:
        parser.exit(1, f'Error: {error}\n')
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result['rejected'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
