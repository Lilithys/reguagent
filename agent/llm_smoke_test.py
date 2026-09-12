#!/usr/bin/env python3
"""Manual connectivity check -- needs a real key and network, so it's not part of
the offline unittest suite. Run after setting ANTHROPIC_API_KEY (or LLM_API_KEY +
LLM_BASE_URL for another provider, e.g. DeepSeek's Anthropic-compatible endpoint):

  export LLM_API_KEY=sk-...
  export LLM_BASE_URL=https://api.deepseek.com/anthropic
  export LLM_MODEL=deepseek-flash   # check DeepSeek's current docs for the live name
  .venv/bin/python agent/llm_smoke_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import complete

if __name__ == '__main__':
    reply = complete(
        system='Reply with exactly one word.',
        user='What is the capital of Ireland?')
    print('Model replied:', reply.strip())
