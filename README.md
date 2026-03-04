# AI-Oscar 2.0

Personal AI persona system running locally on Ollama.

---

## How it works

A Python HTTP server handles all requests. On startup it loads a JSONL 
knowledge base, then for each query retrieves the most relevant context 
using a weighted similarity scoring function (SequenceMatcher + token overlap), 
constructs a persona-aware prompt, and passes it to a local Ollama LLM for 
response generation.

A PHP control interface manages the Python server process — start, stop, 
and health checks via PID file and socket monitoring.

---

## Stack

Python · PHP · Ollama · HTML/CSS

---

## Models used

- qwen2.5:3b-instruct — response generation
- nomic-embed-text — embeddings (planned upgrade to replace string matching retrieval)

---

*Personal project — 2025–2026*
