#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
import subprocess
from difflib import SequenceMatcher
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

HOST = "localhost"
PORT = 8090
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = Path(__file__).resolve().parent
PERSONA_FILE = WEB_DIR / "persona_profile.json"
KNOWLEDGE_FILE = WEB_DIR / "knowledge.jsonl"
OLLAMA_MODEL = "qwen2.5:3b-instruct"
TOP_K = 5


def normalize(text: str) -> str:
    return " ".join(text.split()).strip()


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))


def load_persona() -> dict:
    if not PERSONA_FILE.exists():
        return {}
    return json.loads(PERSONA_FILE.read_text(encoding="utf-8"))


def load_knowledge_rows() -> list[dict]:
    if not KNOWLEDGE_FILE.exists():
        return []
    rows: list[dict] = []
    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and "text" in row and "source" in row:
                rows.append(row)
    return rows


def score(question: str, snippet: str) -> float:
    q = normalize(question.lower())
    s = normalize(snippet.lower())
    ratio = SequenceMatcher(None, q, s).ratio()
    q_tokens = tokenize(q)
    s_tokens = tokenize(s)
    overlap = len(q_tokens & s_tokens) / max(1, len(q_tokens))
    return (0.55 * overlap) + (0.45 * ratio)


def retrieve(question: str, snippets: list[dict], k: int = TOP_K) -> list[dict]:
    ranked = sorted(
        snippets,
        key=lambda row: score(question, row["text"]),
        reverse=True,
    )
    return ranked[:k]


def build_fallback_answer(question: str, matches: list[dict]) -> str:
    if not matches:
        return "I don't have enough information yet. Rebuild persona/knowledge and ask again."

    top = matches[0]["text"]
    if len(top) > 700:
        top = top[:700].rstrip() + "..."

    return (
        f"Based on your profile notes, the best match for '{question}' is:\n\n"
        f"{top}\n\n"
        f"Source: {matches[0]['source']}"
    )


def build_system_prompt(persona: dict) -> str:
    comm = persona.get("communication_style", {})
    do = persona.get("do", [])
    avoid = persona.get("avoid", [])
    values = persona.get("core_values", [])
    summary = persona.get("identity_summary", "")

    lines = [
        "You are Oscar-AI, a personal assistant modeled from Oscar's notes.",
        "Answer in English.",
        "Stay grounded in the provided context only. If context is missing, clearly say so.",
        f"Identity summary: {summary}",
        f"Communication style: {json.dumps(comm, ensure_ascii=False)}",
        f"Core values: {', '.join(values)}",
        f"Do: {' | '.join(do)}",
        f"Avoid: {' | '.join(avoid)}",
    ]
    return "\n".join(lines)


def build_user_prompt(question: str, matches: list[dict]) -> str:
    context_lines = []
    for i, row in enumerate(matches, start=1):
        text = normalize(str(row.get("text", "")))
        if len(text) > 900:
            text = text[:900].rstrip() + "..."
        context_lines.append(f"[{i}] source={row.get('source','unknown')}\n{text}")

    context = "\n\n".join(context_lines) if context_lines else "No context found."
    return (
        "Answer this question using only the context.\n"
        f"Question: {question}\n\n"
        f"Context:\n{context}"
    )


def call_ollama(system_prompt: str, user_prompt: str) -> str | None:
    prompt = f"{system_prompt}\n\n{user_prompt}"
    try:
        p = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return None
    if p.returncode != 0:
        return None
    out = (p.stdout or "").strip()
    return out or None


def build_answer(question: str, matches: list[dict], persona: dict) -> tuple[str, str]:
    if not matches:
        return (build_fallback_answer(question, matches), "fallback")
    system_prompt = build_system_prompt(persona)
    user_prompt = build_user_prompt(question, matches)
    llm_answer = call_ollama(system_prompt, user_prompt)
    if llm_answer:
        return (llm_answer, "ollama")
    return (build_fallback_answer(question, matches), "fallback")


PERSONA_CACHE = load_persona()
KNOWLEDGE_CACHE = load_knowledge_rows()


class Handler(BaseHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if parsed.path == "/styles.css":
            return self._send_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
        if parsed.path == "/api/health":
            return self._send_json({"ok": True})

        self.send_error(404, "Not Found")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/ask":
            return self._send_json({"error": "Not found"}, status=404)

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)

        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return self._send_json({"error": "Invalid JSON"}, status=400)

        question = normalize(str(payload.get("question", "")))
        if not question:
            return self._send_json({"error": "Question is required"}, status=400)

        matches = retrieve(question, KNOWLEDGE_CACHE)
        answer, mode = build_answer(question, matches, PERSONA_CACHE)

        return self._send_json(
            {
                "answer": answer,
                "matches": matches,
                "mode": mode,
            }
        )


def main() -> None:
    if not WEB_DIR.exists():
        raise SystemExit(f"Missing web directory: {WEB_DIR}")

    server = HTTPServer((HOST, PORT), Handler)
    print(f"Oscar-WIO server running: http://{HOST}:{PORT}")
    print(f"Persona file: {PERSONA_FILE}")
    print(f"Knowledge file: {KNOWLEDGE_FILE}")
    print(f"Knowledge rows loaded: {len(KNOWLEDGE_CACHE)}")
    server.serve_forever()


if __name__ == "__main__":
    main()
