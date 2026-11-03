#!/usr/bin/env python3
"""Extract 13 figures from Doc-to-LoRA arXiv v1 using verified PDF crop rectangles.

Produces 288-DPI PNGs and standalone vector-preserving cropped PDFs.
Coordinates correspond to arXiv:2602.15902v1, 28-page paper.
"""
from pathlib import Path
import argparse
import fitz

FIGURES = {
    1: (2, (54, 62, 542, 242)),
    2: (4, (307, 60, 541, 364)),
    3: (6, (54, 57, 543, 246)),
    4: (7, (54, 160, 542, 318)),
    5: (13, (54, 220, 543, 423)),
    6: (14, (131, 309, 464, 415)),
    7: (16, (54, 60, 543, 432)),
    8: (17, (54, 59, 543, 736)),
    9: (18, (126, 62, 482, 273)),
    10: (20, (54, 125, 543, 625)),
    11: (21, (54, 294, 543, 457)),
    12: (22, (54, 124, 543, 628)),
    13: (23, (54, 294, 543, 457)),
}


def extract(pdf_path: Path, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    src = fitz.open(pdf_path)
    if len(src) != 28:
        raise RuntimeError(f"Expected 28 pages for arXiv v1, got {len(src)}. Refusing potentially inaccurate crops.")
    manifest = [
        "# Doc-to-LoRA — extracted figures",
        "",
        "Source: R. Charakorn et al. (2026), *Doc-to-LoRA: Learning to Instantly Internalize Contexts*, arXiv:2602.15902v1.",
        "",
        "Cropped directly from the original PDF. PNGs rendered at 288 DPI; companion PDF pages preserve original vector content.",
        "",
        "| Figure | Original PDF page | PNG | PDF |",
        "|---|---:|---|---|",
    ]
    for figure_id, (page_number, rect) in FIGURES.items():
        page = src[page_number - 1]
        clip = fitz.Rect(*rect)
        if not page.rect.contains(clip):
            raise ValueError(f"Figure {figure_id} crop exceeds page bounds")
        stem = f"Figure_{figure_id:02d}"

        pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=clip, alpha=False)
        pix.save(str(outdir / f"{stem}.png"))

        dest = fitz.open()
        new_page = dest.new_page(width=clip.width, height=clip.height)
        new_page.show_pdf_page(new_page.rect, src, page_number - 1, clip=clip, keep_proportion=False)
        dest.save(str(outdir / f"{stem}.pdf"), garbage=4, deflate=True)
        dest.close()

        manifest.append(f"| Figure {figure_id} | {page_number} | [PNG]({stem}.png) | [PDF]({stem}.pdf) |")
        print(f"Extracted {stem} from PDF page {page_number}", flush=True)

    (outdir / "README.md").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    src.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, default=Path("Doc-to-LoRA"))
    args = parser.parse_args()
    extract(args.pdf, args.output)
