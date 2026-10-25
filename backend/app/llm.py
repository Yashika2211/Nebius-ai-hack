"""Single entry point for Nemotron calls on Nebius Token Factory.

Every call is routed to a tier, timed, costed, cached and recorded in the agent trace.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from functools import lru_cache
from typing import Any, Callable

from openai import OpenAI

from . import db, trace
from .config import settings
from .router import Tier, cost, route


class LLMUnavailable(RuntimeError):
    """No API key and no cached response for this call."""


@lru_cache(maxsize=1)
def client() -> OpenAI:
    return OpenAI(base_url=settings.nebius_base_url, api_key=settings.nebius_api_key or "missing", timeout=120)


def _cache_key(tier: Tier, messages: list[dict], json_mode: bool) -> str:
    raw = json.dumps({"tier": tier, "messages": messages, "json": json_mode}, sort_keys=True)
    return "llm:" + hashlib.sha256(raw.encode()).hexdigest()


_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def clean(text: str) -> str:
    """Strip reasoning blocks some Nemotron variants emit before the answer."""
    text = _THINK.sub("", text or "")
    if "</think>" in text:  # opening tag was consumed by the template
        text = text.split("</think>", 1)[1]
    return text.strip()


def parse_json(text: str) -> Any:
    """Parse JSON from a model reply, tolerating code fences and surrounding prose."""
    text = clean(text)
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start, end = text.find(open_ch), text.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Model did not return valid JSON: {text[:200]}")


def chat(
    task: str,
    messages: list[dict],
    *,
    json_mode: bool = False,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    escalate: int = 0,
    on_token: Callable[[str], None] | None = None,
) -> str:
    """Run a chat completion for `task` on the routed Nemotron tier and return the text."""
    from .models import resolve_models

    tier, reason = route(task, escalate)
    model = resolve_models()[tier]
    key = _cache_key(tier, messages, json_mode)
    event: dict[str, Any] = {
        "kind": "llm",
        "task": task,
        "tier": tier,
        "model": model,
        "reason": reason,
    }

    cached = db.cache_get(key) if settings.demo_mode != "live" else None
    use_cache = cached is not None and (settings.demo_mode == "replay" or not settings.has_llm)
    if use_cache:
        return _finish(event, cached, cached=True, latency_ms=0)
    if not settings.has_llm:
        raise LLMUnavailable(f"NEBIUS_API_KEY is not set and no cached response for {task}")

    start = time.perf_counter()
    try:
        text, usage = _call(model, messages, json_mode, max_tokens, temperature, on_token)
    except Exception as exc:
        if cached is not None and settings.demo_mode == "auto":
            event["error"] = f"live call failed, served cache: {exc}"
            return _finish(event, cached, cached=True, latency_ms=int((time.perf_counter() - start) * 1000))
        trace.emit({**event, "status": "error", "error": str(exc)})
        raise
    latency_ms = int((time.perf_counter() - start) * 1000)
    result = {"text": text, **usage}
    db.cache_put(key, result)
    return _finish(event, result, cached=False, latency_ms=latency_ms)


def _call(model, messages, json_mode, max_tokens, temperature, on_token) -> tuple[str, dict]:
    kwargs: dict[str, Any] = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    if on_token is None:
        resp = client().chat.completions.create(**kwargs)
        usage = resp.usage
        return clean(resp.choices[0].message.content or ""), {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        }

    parts: list[str] = []
    usage = None
    stream = client().chat.completions.create(**kwargs, stream=True, stream_options={"include_usage": True})
    for chunk in stream:
        if chunk.usage:
            usage = chunk.usage
        if chunk.choices and chunk.choices[0].delta.content:
            delta = chunk.choices[0].delta.content
            parts.append(delta)
            on_token(delta)
    text = "".join(parts)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or _estimate_tokens(json.dumps(messages))
    completion_tokens = getattr(usage, "completion_tokens", 0) or _estimate_tokens(text)
    return clean(text), {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _finish(event: dict, result: dict, *, cached: bool, latency_ms: int) -> str:
    pt, ct = result.get("prompt_tokens", 0), result.get("completion_tokens", 0)
    event.update(
        status="ok",
        cached=cached,
        latency_ms=latency_ms,
        prompt_tokens=pt,
        completion_tokens=ct,
        cost=cost(event["tier"], pt, ct),
    )
    trace.emit(event)
    return result["text"]


def chat_json(task: str, system: str, user: str, **kwargs) -> Any:
    """Chat call that must return JSON; retries once with a repair instruction."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    text = chat(task, messages, json_mode=True, **kwargs)
    try:
        return parse_json(text)
    except ValueError:
        messages += [
            {"role": "assistant", "content": text},
            {"role": "user", "content": "That was not valid JSON. Reply with only the JSON object."},
        ]
        return parse_json(chat(task, messages, json_mode=True, **kwargs))
