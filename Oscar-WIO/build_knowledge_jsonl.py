#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "Oscar-Personality"
OUTPUT_FILE = Path(__file__).resolve().parent / "knowledge.jsonl"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 140


HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")


def normalize(text: str) -> str:
    return " ".join(text.split()).strip()


def detect_doc_type(filename: str) -> str:
    name = filename.lower()
    if name.startswith("person"):
        return "person"
    if name.startswith("school"):
        return "school"
    return "general"


def extract_headings(lines: list[str]) -> list[str]:
    headings = []
    for line in lines:
        m = HEADING_RE.match(line.strip())
        if m:
            headings.append(normalize(m.group(1)))
    return headings


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text:
        return []
    clean = normalize(text)
    if len(clean) <= size:
        return [clean]

    chunks = []
    step = max(1, size - overlap)
    for start in range(0, len(clean), step):
        part = clean[start:start + size]
        if len(part) < 120:
            continue
        chunks.append(part)
        if start + size >= len(clean):
            break
    return chunks


def load_markdown_files(base: Path) -> list[Path]:
    return sorted([p for p in base.rglob("*.md") if p.is_file() and not p.name.startswith(".")])


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def build_rows() -> list[dict]:
    rows = []
    files = load_markdown_files(SOURCE_DIR)
    for path in files:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        lines = raw.splitlines()
        headings = extract_headings(lines)
        doc_type = detect_doc_type(path.name)
        chunks = chunk_text(raw)

        for idx, chunk in enumerate(chunks, start=1):
            row = {
                "id": f"{path.stem}__{idx}",
                "source": str(path.relative_to(ROOT)),
                "file": path.name,
                "doc_type": doc_type,
                "chunk_index": idx,
                "chunk_chars": len(chunk),
                "chunk_tokens_est": estimate_tokens(chunk),
                "headings": headings[:10],
                "text": chunk,
            }
            rows.append(row)
    return rows


def main() -> int:
    rows = build_rows()
    if not rows:
        raise SystemExit(f"No chunks generated from: {SOURCE_DIR}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote: {OUTPUT_FILE}")
    print(f"Rows: {len(rows)}")
    print(f"Source dir: {SOURCE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
