> **Disclaimer**: This repository is for educational and research purposes only; it provides no investment advice or guarantees.
# Ollama LLM Request Serialization Specification

## Background
Running multiple analyst agents in parallel can result in concurrent requests to a local Ollama server. Because Ollama may process only one request efficiently at a time, parallel requests can cause contention and overall slowdown. The current code invokes `llm.invoke` directly for every agent, so calls are not synchronized.

## Goal
Ensure that only one Ollama request is active at any moment. This prevents local resources from being oversubscribed and provides more predictable throughput.

## Implementation Overview
1. **Add a lock in `src/utils/llm.py`**
   - Import `threading` and `ModelProvider` at the top of the file.
   - Define a module‑level `ollama_lock = threading.Lock()`.

2. **Wrap Ollama calls with the lock**
   - In `call_llm`, check if the selected provider equals `ModelProvider.OLLAMA.value`.
   - When it does, wrap `llm.invoke(prompt)` in a `with ollama_lock:` block so only one thread can call Ollama at a time.
   - Leave the existing retry logic and non‑Ollama providers unchanged.

3. **Documentation**
   - Note in the README that local LLM requests are serialized when using `--ollama`.

4. **Testing**
   - Run the workflow with multiple analysts and verify that requests do not overlap. Unit tests may mock the lock to confirm serialization.

## File Changes Summary
- `src/utils/llm.py` – introduce the lock and guard `llm.invoke` when provider is Ollama.
- `README.md` – mention request serialization in the Ollama usage section.

