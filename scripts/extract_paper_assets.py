#!/usr/bin/env python3
"""Reproducible high-resolution PNG extraction for figures AND tables in research PDFs.

Usage:
    python scripts/extract_paper_assets.py --manifest manifests/doc-to-lora-2026.json --pdf local.pdf
    python scripts/extract_paper_assets.py --manifest manifests/doc-to-lora-2026.json
    python scripts/extract_paper_assets.py --all

Crop rectangles are specified in PDF points (72/in), origin top-left; PDF pages are 1-based.
No cropped PDF files are ever produced. Human-reviewed rectangles are required in manifests.
All outputs must be under Papers/<Paper-Name>/.
"""
from __future__ import annotations

import argparse
import math
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import fitz

BASE_DIR = Path(__file__).resolve().parent.parent
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,50}$")
CAPTION_RE = re.compile(r"^\s*(Figure|Table)\s+((?:[A-Za-z]\.?)?\d+[A-Za-z]?)\s*[.:|]", re.I)


def paper_caption_locations(pdf: fitz.Document) -> dict[str, dict[str, int]]:
    """Find captions beginning a line, including those in appendix; never count prose mentions."""
    found = {"figures": {}, "tables": {}}
    for page_no, page in enumerate(pdf, start=1):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                line_text = "".join(span["text"] for span in line["spans"]).strip()
                match = CAPTION_RE.match(line_text)
                if match:
                    category = "figures" if match.group(1).lower() == "figure" else "tables"
                    number = match.group(2).upper().replace(".", "")
                    previous = found[category].get(number)
                    if previous is not None and previous != page_no:
                        raise ValueError(f"Ambiguous caption {category} {number} on pages {previous}, {page_no}")
                    found[category][number] = page_no
    return found


def validate_manifest(config: dict, pdf: fitz.Document) -> dict:
    required = ("slug", "title", "source_urls", "expected_pages", "output_dir", "figures", "tables")
    for key in required:
        if key not in config:
            raise ValueError(f"Manifest missing key: {key}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", config["slug"]):
        raise ValueError("slug must contain only lowercase letters, digits and hyphens")
    out = Path(config["output_dir"])
    # Keep the repository root free of per-paper directories.
    if (out.is_absolute() or len(out.parts) != 2 or out.parts[0] != "Papers"
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", out.parts[1])):
        raise ValueError("output_dir must be Papers/<Paper-Name> (one ASCII slug directory)")
    expected_pages = int(config["expected_pages"])
    if len(pdf) != expected_pages:
        raise ValueError(f"Source PDF mismatch: expected {expected_pages} pages, got {len(pdf)}")
    captions = paper_caption_locations(pdf)
    for kind in ("figures", "tables"):
        entries = config[kind]
        if not isinstance(entries, list):
            raise ValueError(f"{kind} must be a list")
        keys = []
        for obj in entries:
            key = str(obj["id"]).upper()
            if not ID_RE.fullmatch(key):
                raise ValueError(f"Invalid {kind} id: {key}")
            keys.append(key)
            page_no = int(obj["page"])
            if page_no < 1 or page_no > len(pdf):
                raise ValueError(f"Page {page_no} out of range for {kind} {key}")
            rect = fitz.Rect(*obj["rect"])
            if rect.is_empty or rect.is_infinite or not pdf[page_no - 1].rect.contains(rect):
                raise ValueError(f"Invalid rectangle for {kind} {key}: {rect}")
            cap_page = int(obj.get("caption_page", page_no))
            if captions[kind].get(key) != cap_page:
                raise ValueError(
                    f"Caption mismatch for {kind} {key}: expected PDF page {cap_page}, "
                    f"found on {captions[kind].get(key)!r}. Check PDF version and crop coordinates."
                )
        if len(keys) != len(set(keys)):
            raise ValueError(f"Repeated IDs in {kind}")
        absent = sorted(set(captions[kind]) - set(keys))
        extra = sorted(set(keys) - set(captions[kind]))
        if absent or extra:
            raise ValueError(f"Coverage mismatch for {kind}: missing {absent}, undocumented {extra}")
    return captions


def download_pdf(urls: list[str], destination: Path) -> None:
    failures = []
    for url in urls:
        url_parts = urlparse(url)
        if url_parts.scheme != "https" or not url_parts.netloc:
            failures.append(f"Not an HTTPS URL: {url}")
            continue
        proc = subprocess.run(
            ["curl", "-fSL", "--retry", "4", "--retry-delay", "3", "--retry-all-errors",
             "--connect-timeout", "20", "--max-time", "160", "-A", "Mozilla/5.0 (research paper asset archiver)",
             "-o", str(destination), url], capture_output=True, text=True,
        )
        if proc.returncode == 0 and destination.exists() and destination.read_bytes()[:5] == b"%PDF-":
            print(f"Downloaded source PDF from {url}")
            return
        failures.append(f"Download failed ({proc.returncode}) for {url}: {proc.stderr[-400:]}")
    raise RuntimeError("Could not download a valid PDF. Use --pdf with local source. " + "; ".join(failures))


def stem_for(kind: str, item_id: str) -> str:
    key = str(item_id).upper()
    if key.isdigit():
        key = f"{int(key):02d}"
    return ("Figure_" if kind == "figures" else "Table_") + key


def extract_one(config: dict, pdf_path: Path) -> tuple[Path, int, int]:
    pdf = fitz.open(str(pdf_path))
    validate_manifest(config, pdf)
    output = BASE_DIR / config["output_dir"]
    scale = float(config.get("render_scale", 4))
    if not (2 <= scale <= 12):
        raise ValueError("render_scale must be 2..12; 4 means 288 DPI")
    dpi = int(round(72 * scale))
    lines = [
        f"# {config['title']} — Figures and Tables",
        "",
        f"Original paper: {config.get('citation', config['title'])}  ",
        f"Source: {config['source_urls'][0]}  ",
        f"PDF version: {config.get('source_version', 'as specified in manifest')}  ",
        f"Output: **PNG only**, rendered at **{dpi} DPI** from original PDF vector/text content.",
        "",
        "Crop rectangles and PDF page numbers are recorded in the [manifest]"
        f"(../../manifests/{config['slug']}.json). The original source must match the manifest version.",
        "",
    ]
    for kind in ("figures", "tables"):
        folder = output / kind
        folder.mkdir(parents=True, exist_ok=True)
        singular = "Figure" if kind == "figures" else "Table"
        lines += [f"## {singular}s ({len(config[kind])})", "", f"| {singular} | Original PDF page | Preview | Obsidian / Markdown |", "|---|---:|---|---|"]
        for item in config[kind]:
            number = str(item["id"]).upper()
            page_no = int(item["page"])
            rect = fitz.Rect(*item["rect"])
            file_name = stem_for(kind, number) + ".png"
            target = folder / file_name
            pix = pdf[page_no - 1].get_pixmap(matrix=fitz.Matrix(scale, scale), clip=rect, alpha=False)
            pix.set_dpi(dpi, dpi)
            if pix.width < 70 or pix.height < 50:
                raise ValueError(f"Very small crop for {singular} {number}")
            pix.save(str(target))
            # A relative path is intentional inside the repository index; use raw URL for external notes.
            rel = f"{kind}/{file_name}"
            raw_url = f"https://raw.githubusercontent.com/{config.get('repository','AsukirinaAI/Paper-figures')}/main/{config['output_dir']}/{rel}"
            img_md = f"![{singular} {number}]({raw_url})"
            lines.append(f"| {singular} {number} | {page_no} | ![{singular} {number}]({rel}) | `{img_md}` |")
            print(f"{config['slug']}: {singular} {number} <- PDF p.{page_no} {rect}; {pix.width}x{pix.height} px")
        lines.append("")
    lines += ["## Reuse & attribution", "",
              "These are unaltered crops of the original authors' figures and tables (not redrawn).",
              "Credit the original paper and comply with its applicable license when reusing assets.",
              "See [the repository-wide workflow](../../docs/PAPER_ASSET_WORKFLOW.md) for conventions.", ""]
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    # Old vector PDF artifacts are intentionally removed; the input source PDF is elsewhere.
    for folder in (output, output / "figures", output / "tables"):
        for path in folder.glob("*.pdf"):
            path.unlink()
    pdf.close()
    return output, len(config["figures"]), len(config["tables"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--manifest", type=Path, help="Repository-relative or absolute JSON crop manifest")
    group.add_argument("--all", action="store_true", help="Process all manifests/*.json")
    parser.add_argument("--pdf", type=Path, help="Use local PDF (only valid for --manifest)")
    args = parser.parse_args()
    if args.pdf and args.all:
        parser.error("--pdf requires exactly one --manifest")
    manifests = sorted((BASE_DIR / "manifests").glob("*.json")) if args.all else [args.manifest]
    if not manifests:
        raise RuntimeError("No manifests found")
    for manifest in manifests:
        if not manifest.is_absolute():
            manifest = BASE_DIR / manifest
        config = json.loads(manifest.read_text(encoding="utf-8"))
        if not config.get("source_urls"):
            raise ValueError("A public source PDF URL is required")
        if args.pdf:
            out, f_count, t_count = extract_one(config, args.pdf)
        else:
            with tempfile.TemporaryDirectory(prefix="paper-asset-") as dirname:
                source = Path(dirname) / "source.pdf"
                download_pdf(config["source_urls"], source)
                out, f_count, t_count = extract_one(config, source)
        print(f"SUCCESS: {out} contains {f_count} figures and {t_count} tables (PNG only).")


if __name__ == "__main__":
    main()
