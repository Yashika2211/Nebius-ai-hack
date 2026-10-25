"""Agent trace: every model and tool call is recorded and streamed to the UI."""
from __future__ import annotations

import asyncio
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from . import db
from .router import savings


@dataclass
class Trace:
    label: str
    id: str = field(default_factory=db.new_id)
    events: list[dict] = field(default_factory=list)
    started: float = field(default_factory=time.time)
    queue: asyncio.Queue | None = None
    loop: asyncio.AbstractEventLoop | None = None

    def emit(self, event: dict[str, Any]) -> dict:
        event.setdefault("ts", time.time())
        event["seq"] = len(self.events)
        self.events.append(event)
        self.publish({"type": "trace", "event": event})
        return event

    def publish(self, message: dict) -> None:
        """Push a message to the SSE stream, if one is attached. Safe from worker threads."""
        if self.queue is None or self.loop is None:
            return
        self.loop.call_soon_threadsafe(self.queue.put_nowait, message)

    def summary(self) -> dict:
        llm = [e for e in self.events if e.get("kind") == "llm"]
        return {
            "id": self.id,
            "label": self.label,
            "started": self.started,
            "duration_ms": int((time.time() - self.started) * 1000),
            "llm_calls": len(llm),
            "tool_calls": len([e for e in self.events if e.get("kind") == "tool"]),
            "prompt_tokens": sum(e.get("prompt_tokens", 0) for e in llm),
            "completion_tokens": sum(e.get("completion_tokens", 0) for e in llm),
            "savings": savings(self.events),
        }

    def finish(self) -> dict:
        data = {**self.summary(), "events": self.events}
        db.save_trace(self.id, self.label, data)
        return data


_current: ContextVar[Trace | None] = ContextVar("current_trace", default=None)


def current() -> Trace | None:
    return _current.get()


def start(label: str, queue: asyncio.Queue | None = None) -> Trace:
    loop = None
    if queue is not None:
        loop = asyncio.get_running_loop()
    trace = Trace(label=label, queue=queue, loop=loop)
    _current.set(trace)
    return trace


def use(trace: Trace):
    """Bind an existing trace to the current context (e.g. inside a worker thread)."""
    return _current.set(trace)


def emit(event: dict[str, Any]) -> dict | None:
    trace = current()
    return trace.emit(event) if trace else None


def step(name: str, detail: str = "") -> None:
    """Record a high-level pipeline step (shown as a header in the trace panel)."""
    emit({"kind": "step", "name": name, "detail": detail})
