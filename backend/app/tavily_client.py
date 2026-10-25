"""Tavily search, extract and crawl, with caching and trace events.

How BidScout uses each endpoint:
- crawl:   onboarding. Walks a company site (about, services, past performance pages)
           so the profile is built from the whole site, not just the homepage.
- search:  discovery. Finds live solicitations across SAM.gov and state/city portals.
- extract: depth. Pulls the full text of a chosen RFP page so eligibility and the
           compliance matrix are grounded in the actual solicitation language.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import httpx

from . import db, trace
from .config import settings

BASE = "https://api.tavily.com"


class SearchUnavailable(RuntimeError):
    pass


def _key(endpoint: str, payload: dict) -> str:
    raw = json.dumps({"e": endpoint, "p": payload}, sort_keys=True)
    return "tavily:" + hashlib.sha256(raw.encode()).hexdigest()


def _post(endpoint: str, payload: dict, summary: str, timeout: float = 60) -> dict:
    key = _key(endpoint, payload)
    cached = db.cache_get(key) if settings.demo_mode != "live" else None
    event: dict[str, Any] = {"kind": "tool", "tool": f"tavily.{endpoint}", "detail": summary}

    if cached is not None and (settings.demo_mode == "replay" or not settings.has_search):
        trace.emit({**event, "status": "ok", "cached": True, "latency_ms": 0, "results": _count(cached)})
        return cached
    if not settings.has_search:
        raise SearchUnavailable(f"TAVILY_API_KEY is not set and no cached {endpoint} result")

    start = time.perf_counter()
    try:
        resp = httpx.post(
            f"{BASE}/{endpoint}",
            json=payload,
            headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        latency = int((time.perf_counter() - start) * 1000)
        if cached is not None and settings.demo_mode == "auto":
            trace.emit({**event, "status": "ok", "cached": True, "latency_ms": latency,
                        "results": _count(cached), "error": f"live call failed, served cache: {exc}"})
            return cached
        trace.emit({**event, "status": "error", "latency_ms": latency, "error": str(exc)})
        raise
    db.cache_put(key, data)
    trace.emit({**event, "status": "ok", "cached": False,
                "latency_ms": int((time.perf_counter() - start) * 1000), "results": _count(data)})
    return data


def _count(data: dict) -> int:
    return len(data.get("results") or [])


def search(query: str, *, max_results: int = 8, include_domains: list[str] | None = None,
           days: int | None = None) -> list[dict]:
    payload: dict[str, Any] = {
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_raw_content": False,
    }
    if include_domains:
        payload["include_domains"] = include_domains
    if days:
        payload["time_range"] = "month" if days <= 31 else "year"
    return _post("search", payload, f"search: {query}").get("results", [])


def extract(urls: list[str], *, depth: str = "advanced") -> list[dict]:
    payload = {"urls": urls, "extract_depth": depth}
    return _post("extract", payload, f"extract {len(urls)} page(s)", timeout=90).get("results", [])


def crawl(url: str, *, instructions: str = "", limit: int = 12, max_depth: int = 2) -> list[dict]:
    payload: dict[str, Any] = {"url": url, "limit": limit, "max_depth": max_depth, "extract_depth": "basic"}
    if instructions:
        payload["instructions"] = instructions
    return _post("crawl", payload, f"crawl {url}", timeout=150).get("results", [])
