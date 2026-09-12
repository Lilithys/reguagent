"""Anthropic Messages-compatible adapter for optional drafting and tool-driven tasks.

Existing provider environment variables are retained. No arbitrary code execution
or state mutations occur in this adapter; the application validates all tool calls.
"""
import os
from llm_config import load_local_config

import anthropic

DEFAULT_MODEL = 'claude-sonnet-5'


def _client(timeout: float = 30) -> anthropic.Anthropic:
    load_local_config()
    api_key = os.environ.get('LLM_API_KEY') or os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError(
            'No API key found. Set ANTHROPIC_API_KEY for Anthropic, or LLM_API_KEY '
            '(+ optionally LLM_BASE_URL) for another Anthropic-Messages-API-compatible provider.')
    base_url = os.environ.get('LLM_BASE_URL') or None
    return anthropic.Anthropic(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)


def complete(system: str, user: str, *, max_tokens: int = 2048) -> str:
    """One-shot text completion, no tools, no streaming. Every call site parses and
    validates its own output -- this function never guesses at malformed responses.

    No temperature/top_p here: installed anthropic SDK 1.4.0's Messages.create() no
    longer accepts them (verified by inspecting the installed signature directly --
    sampling controls appear to have moved off this endpoint; output_config now
    covers reasoning effort and structured-output format instead). This is a
    client-side SDK shape, not a DeepSeek quirk -- it fails identically against
    real Anthropic.

    thinking is explicitly disabled: a reasoning model's internal thinking can
    consume the entire max_tokens budget before it ever emits a text block (seen in
    practice -- response.content was `['thinking']` with no text at all). None of
    this codebase's calls (drafting a pairwise-comparison table, extracting a field,
    writing a one-sentence narrative) need deep reasoning, so there's no tradeoff
    being made here, just removing a failure mode.
    """
    model = os.environ.get('LLM_MODEL', DEFAULT_MODEL)
    response = _client().messages.create(
        model=model, max_tokens=max_tokens, thinking={'type': 'disabled'},
        system=system, messages=[{'role': 'user', 'content': user}])
    # A reasoning model may still return a ThinkingBlock ahead of the actual
    # TextBlock even with thinking disabled; content[0] isn't reliably the answer,
    # so find every text block instead.
    text_blocks = [block.text for block in response.content if block.type == 'text']
    if not text_blocks:
        raise RuntimeError(f'No text block in response; got block types: {[b.type for b in response.content]}')
    return ''.join(text_blocks)


class AnthropicToolClient:
    """One HTTP attempt per generate call; bounded retry decisions live in the runner.

    Only normalized text/tool-use blocks leave the adapter. Hidden model reasoning
    is not persisted in the audit trail. There are no silent replay fallbacks.
    """
    mode = 'live'

    def __init__(self):
        self.request_attempts = 0

    def generate(self, *, role, system, messages, tools, max_tokens, timeout):
        client = _client(timeout)
        model = os.environ.get('LLM_MODEL', DEFAULT_MODEL)
        if os.environ.get('LLM_BASE_URL') and not os.environ.get('LLM_MODEL'):
            raise RuntimeError('LLM_MODEL is required for a custom compatible endpoint')
        self.request_attempts += 1
        response = client.messages.create(model=model, max_tokens=max_tokens, system=system,
            messages=messages, tools=tools, tool_choice={'type':'auto'},
            thinking={'type':'disabled'}, timeout=timeout)
        blocks = []
        for block in response.content:
            if block.type == 'text':blocks.append({'type':'text','text':block.text})
            elif block.type == 'tool_use':blocks.append({'type':'tool_use','id':block.id,'name':block.name,'input':block.input})
            elif block.type != 'thinking':raise RuntimeError('Unsupported response content block type')
        return dict(content=blocks, stop_reason=response.stop_reason,
                    usage={'input_tokens':response.usage.input_tokens,'output_tokens':response.usage.output_tokens})
