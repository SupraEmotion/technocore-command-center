"""Read and snapshot public Technocore protocol metadata."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_BASE_URL = "https://technocore.chat"

ENDPOINTS = {
    "config": "/config",
    "agent_manifest": "/.well-known/agent.json",
    "openapi": "/openapi.json",
    "skill": "/skill.md",
    "patterns": "/patterns.md",
    "interop": "/interop.md",
}


@dataclass
class Observation:
    name: str
    path: str
    status: int | None
    content_type: str | None
    body: str | None
    error: str | None
    observed_at: float


def fetch(
    base_url: str,
    name: str,
    path: str,
    timeout: float = 20.0,
) -> Observation:
    url = base_url.rstrip("/") + path

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "Technocore-Command-Center/observatory",
        },
    )

    observed_at = time.time()

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")

            return Observation(
                name=name,
                path=path,
                status=response.status,
                content_type=response.headers.get("Content-Type"),
                body=body,
                error=None,
                observed_at=observed_at,
            )

    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = ""

        return Observation(
            name=name,
            path=path,
            status=exc.code,
            content_type=exc.headers.get("Content-Type"),
            body=error_body,
            error=f"HTTP {exc.code}",
            observed_at=observed_at,
        )

    except Exception as exc:
        return Observation(
            name=name,
            path=path,
            status=None,
            content_type=None,
            body=None,
            error=f"{type(exc).__name__}: {exc}",
            observed_at=observed_at,
        )


def snapshot(
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 20.0,
) -> list[Observation]:
    return [
        fetch(base_url, name, path, timeout)
        for name, path in ENDPOINTS.items()
    ]


def parse_json(observation: Observation) -> dict[str, Any] | None:
    if not observation.body:
        return None

    try:
        value = json.loads(observation.body)
    except json.JSONDecodeError:
        return None

    return value if isinstance(value, dict) else None


def summary(observations: list[Observation]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "observed_at": max(
            (item.observed_at for item in observations),
            default=time.time(),
        ),
        "endpoints": {},
    }

    for item in observations:
        entry: dict[str, Any] = {
            "path": item.path,
            "status": item.status,
            "content_type": item.content_type,
            "error": item.error,
            "bytes": len(item.body.encode("utf-8")) if item.body else 0,
        }

        parsed = parse_json(item)

        if item.name == "config" and parsed:
            entry["version"] = parsed.get("version")
            entry["config"] = parsed

        if item.name == "agent_manifest" and parsed:
            entry["agent_manifest"] = parsed

        result["endpoints"][item.name] = entry

    return result
