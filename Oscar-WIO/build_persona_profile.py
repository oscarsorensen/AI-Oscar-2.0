#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "Oscar-Personality"
OUTPUT_FILE = Path(__file__).resolve().parent / "persona_profile.json"

WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'_-]*")
SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "you", "your", "are", "was", "have",
    "has", "had", "his", "her", "she", "him", "its", "not", "but", "can", "will", "all", "into",
    "about", "there", "their", "what", "when", "where", "which", "how", "why", "who", "than", "then",
    "also", "because", "been", "being", "more", "most", "very", "some", "such", "only", "over", "under",
    "between", "after", "before", "they", "them", "were", "our", "out", "any", "may", "might", "should",
}


def normalize(text: str) -> str:
    return " ".join(text.split()).strip()


def load_markdown_files(base: Path) -> list[Path]:
    return sorted([p for p in base.rglob("*.md") if p.is_file() and not p.name.startswith(".")])


def top_sentences(text: str, limit: int = 8) -> list[str]:
    parts = [normalize(s) for s in SPLIT_RE.split(text) if normalize(s)]
    ranked = sorted(parts, key=lambda s: len(s), reverse=True)
    out = []
    seen = set()
    for sentence in ranked:
        low = sentence.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(sentence)
        if len(out) >= limit:
            break
    return out


def top_keywords(text: str, limit: int = 40) -> list[str]:
    counter = Counter()
    for token in WORD_RE.findall(text.lower()):
        if len(token) < 4 or token in STOPWORDS:
            continue
        counter[token] += 1
    return [w for w, _ in counter.most_common(limit)]


def infer_communication_style(text: str) -> dict[str, str]:
    text_l = text.lower()
    style = {
        "clarity": "high",
        "tone": "direct, analytical, pragmatic",
        "verbosity": "medium",
        "decision_style": "evidence-driven and iterative",
    }
    if "minimal" in text_l or "concise" in text_l:
        style["verbosity"] = "low-to-medium"
    if "friendly" in text_l:
        style["tone"] = "direct, friendly, pragmatic"
    return style


def infer_values(keywords: list[str]) -> list[str]:
    buckets = {
        "learning": {"learning", "study", "school", "education", "progress", "skills", "practice"},
        "building": {"build", "system", "project", "implementation", "product", "prototype"},
        "autonomy": {"autonomy", "independent", "freedom", "self", "ownership"},
        "efficiency": {"efficient", "efficiency", "optimize", "focus", "priority", "output"},
        "clarity": {"clarity", "structure", "logic", "rigor", "analysis"},
    }
    present = []
    kw = set(keywords)
    for name, trigger in buckets.items():
        if kw & trigger:
            present.append(name)
    return present


def build_profile() -> dict:
    files = load_markdown_files(SOURCE_DIR)
    if not files:
        raise SystemExit(f"No .md files found in {SOURCE_DIR}")

    docs = []
    combined_parts = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        clean = normalize(text)
        docs.append({
            "file": str(path.relative_to(ROOT)),
            "chars": len(clean),
        })
        combined_parts.append(clean)

    combined = "\n\n".join(combined_parts)
    keywords = top_keywords(combined)
    evidence = top_sentences(combined, limit=10)

    profile = {
        "profile_version": "1.0",
        "generated_from": {
            "source_dir": str(SOURCE_DIR.relative_to(ROOT)),
            "files": docs,
            "total_files": len(docs),
            "total_chars": len(combined),
        },
        "identity_summary": "Oscar is a practical builder-learner profile focused on real implementation, clear structure, and continuous improvement.",
        "communication_style": infer_communication_style(combined),
        "core_values": infer_values(keywords),
        "dominant_topics": keywords[:20],
        "do": [
            "Give structured, practical answers.",
            "Prefer clear steps and concrete examples.",
            "Connect advice to learning and execution outcomes.",
        ],
        "avoid": [
            "Vague motivational filler.",
            "Unnecessary theory without implementation path.",
            "Contradicting source notes without saying uncertainty.",
        ],
        "evidence_snippets": evidence,
    }
    return profile


def main() -> int:
    profile = build_profile()
    OUTPUT_FILE.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote: {OUTPUT_FILE}")
    print(f"Sources: {profile['generated_from']['total_files']} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
