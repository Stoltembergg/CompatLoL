#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Static references only: neither symbol availability nor fixture license approval."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent


def inventory(source):
    source = Path(source)
    header = source / 'private-include/iridium/dynamic-llvm.hpp'
    names = re.findall(r'_macro\((LLVM\w+)\)', header.read_text())
    if not names or len(names) != len(set(names)):
        raise ValueError('invalid dynamic LLVM symbol list')
    files = sorted((source / 'src/iridium').rglob('*.cpp'))
    symbols = []
    for name in names:
        refs = []
        for path in files:
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if re.search(r'\b' + re.escape(name) + r'\b', line):
                    refs.append({'path': path.relative_to(source).as_posix(), 'line': number})
        symbols.append({'name': name, 'references': refs,
                        'status': 'source-reference-only' if refs else 'declared-not-directly-referenced'})
    fixtures = []
    for path in sorted((source / 'test').rglob('*.metallib')):
        fixtures.append({'relative_path': path.relative_to(source).as_posix(),
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'license_status': 'unconfirmed', 'origin_status': 'unconfirmed',
                         'toolchain': None, 'approved_for_translation': False})
    return {'schema_version': 1, 'symbol_declaration': header.relative_to(source).as_posix(),
            'symbols': symbols, 'fixtures': fixtures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=str(ROOT / '.work/upstream/indium'))
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    result = inventory(args.source)
    # Explicit new output only. Never overwrite an existing source/audit file.
    with Path(args.out).open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')


if __name__ == '__main__':
    main()
