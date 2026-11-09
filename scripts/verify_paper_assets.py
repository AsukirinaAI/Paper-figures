#!/usr/bin/env python3
"""Verify every generated PNG against its published GitHub Raw URL."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from pathlib import Path

import fitz
from extract_paper_assets import stem_for

BASE_DIR = Path(__file__).resolve().parent.parent
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def verify_published_png(url: str, expected: bytes) -> tuple[int, int]:
    expected_hash = hashlib.sha256(expected).digest()
    failure = None
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'paper-asset-verifier', 'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise ValueError(f'Unexpected HTTP status {response.status}')
                data = response.read()
            if not data.startswith(PNG_SIGNATURE):
                raise ValueError('Response is not a PNG')
            if hashlib.sha256(data).digest() != expected_hash:
                raise ValueError('Published PNG differs from the generated file')
            pixmap = fitz.Pixmap(data)
            if pixmap.width < 70 or pixmap.height < 50:
                raise ValueError('Published PNG has unexpectedly small dimensions')
            return pixmap.width, pixmap.height
        except Exception as error:
            failure = error
            if attempt < 4:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'Failed to verify {url}: {failure}') from failure


def main() -> None:
    count = 0
    for manifest in sorted((BASE_DIR / 'manifests').glob('*.json')):
        config = json.loads(manifest.read_text())
        paper_count = 0
        for kind in ('figures', 'tables'):
            expected_paths = {
                BASE_DIR / config['output_dir'] / kind / (stem_for(kind, str(item['id'])) + '.png')
                for item in config[kind]
            }
            actual_paths = set((BASE_DIR / config['output_dir'] / kind).glob('*.png'))
            if actual_paths != expected_paths:
                raise ValueError(f'PNG inventory mismatch for {config["slug"]}/{kind}')
            for local_path in sorted(expected_paths):
                relative = local_path.relative_to(BASE_DIR).as_posix()
                url = f'https://raw.githubusercontent.com/{config.get("repository", "AsukirinaAI/Paper-figures")}/main/{relative}'
                width, height = verify_published_png(url, local_path.read_bytes())
                print(f'VERIFIED {relative}: HTTP 200, PNG {width}x{height}, matching SHA-256', flush=True)
                count += 1
                paper_count += 1
        print(f'VERIFIED {config["slug"]}: {paper_count} published PNGs', flush=True)
    print(f'SUCCESS: verified {count} published PNGs', flush=True)


if __name__ == '__main__':
    main()
