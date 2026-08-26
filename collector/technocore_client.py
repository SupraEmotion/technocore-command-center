from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_BASE_URL = "https://technocore.chat"


@dataclass
class RoomRead:
    room: str
    count: int
    first_seq: int | None
    last_seq: int
    messages: list[dict[str, Any]]


class TechnocoreClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def read_room(
        self,
        room: str,
        since: int = 0,
        limit: int = 200,
        wait: int = 10,
    ) -> RoomRead:
        params = urllib.parse.urlencode(
            {
                "since": since,
                "limit": limit,
                "wait": wait,
                "format": "json",
            }
        )

        url = f"{self.base_url}/r/{urllib.parse.quote(room)}?{params}"

        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json"},
            method="GET",
        )

        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.load(response)

        return RoomRead(
            room=payload["room"],
            count=payload["count"],
            first_seq=payload.get("first_seq"),
            last_seq=payload["last_seq"],
            messages=payload["messages"],
        )
