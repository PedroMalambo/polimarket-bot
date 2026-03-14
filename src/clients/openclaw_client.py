from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from src.config.settings import get_settings


class OpenClawClient:
    def __init__(
        self,
        ws_url: str,
        token: str,
        client_id: str = "gateway-client",
        client_mode: str = "cli",
        client_version: str = "dev",
        platform: str = "linux",
        instance_id: str = "polymarket-bot",
        role: str = "operator",
        scopes: list[str] | None = None,
        caps: list[str] | None = None,
        locale: str = "en",
        open_timeout: float = 10.0,
        request_timeout: float = 45.0,
    ) -> None:
        self.ws_url = ws_url
        self.token = token
        self.client_id = client_id
        self.client_mode = client_mode
        self.client_version = client_version
        self.platform = platform
        self.instance_id = instance_id
        self.role = role
        self.scopes = scopes or ["operator.admin"]
        self.caps = caps or ["tool-events"]
        self.locale = locale
        self.open_timeout = open_timeout
        self.request_timeout = request_timeout

        self.ws: ClientConnection | None = None
        self.last_hello: dict[str, Any] | None = None

    async def __aenter__(self) -> "OpenClawClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def connect(self) -> dict[str, Any]:
        self.ws = await websockets.connect(
            self.ws_url,
            open_timeout=self.open_timeout,
        )

        connect_result = await self.request(
            "connect",
            {
                "minProtocol": 3,
                "maxProtocol": 3,
                "client": {
                    "id": self.client_id,
                    "version": self.client_version,
                    "platform": self.platform,
                    "mode": self.client_mode,
                    "instanceId": self.instance_id,
                },
                "role": self.role,
                "scopes": self.scopes,
                "caps": self.caps,
                "locale": self.locale,
                "auth": {
                    "token": self.token,
                },
            },
        )

        self.last_hello = connect_result
        return connect_result

    async def close(self) -> None:
        if self.ws is not None:
            await self.ws.close()
            self.ws = None

    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.ws is None:
            raise RuntimeError("OpenClaw websocket is not connected")

        req_id = str(uuid.uuid4())
        payload = {
            "type": "req",
            "id": req_id,
            "method": method,
            "params": params,
        }
        await self.ws.send(json.dumps(payload))

        while True:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=self.request_timeout)
            message = json.loads(raw)

            if message.get("type") == "res" and message.get("id") == req_id:
                if not message.get("ok", False):
                    error = message.get("error") or {}
                    raise RuntimeError(
                        f"OpenClaw request failed | method={method} | "
                        f"code={error.get('code')} | "
                        f"message={error.get('message')} | "
                        f"details={error.get('details')}"
                    )
                return message.get("payload") or {}

    async def health(self) -> dict[str, Any]:
        return await self.request("health", {})

    async def chat_send(
        self,
        message: str,
        session_key: str = "main",
        deliver: bool = False,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "sessionKey": session_key,
            "message": message,
            "deliver": deliver,
            "idempotencyKey": str(uuid.uuid4()),
        }
        if attachments:
            params["attachments"] = attachments

        return await self.request("chat.send", params)

    async def chat_history(
        self,
        session_key: str = "main",
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self.request(
            "chat.history",
            {
                "sessionKey": session_key,
                "limit": limit,
            },
        )

    async def chat_abort(
        self,
        session_key: str = "main",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"sessionKey": session_key}
        if run_id:
            params["runId"] = run_id
        return await self.request("chat.abort", params)


def build_openclaw_ws_url(gateway_url: str) -> str:
    value = gateway_url.strip()
    if value.startswith("ws://") or value.startswith("wss://"):
        return value
    if value.startswith("http://"):
        return "ws://" + value[len("http://") :]
    if value.startswith("https://"):
        return "wss://" + value[len("https://") :]
    return value


def get_openclaw_client() -> OpenClawClient:
    settings = get_settings()

    token = settings.OPENCLAW_GATEWAY_TOKEN
    if not token:
        raise RuntimeError("OPENCLAW_GATEWAY_TOKEN is required")

    return OpenClawClient(
        ws_url=build_openclaw_ws_url(settings.OPENCLAW_GATEWAY_URL),
        token=token,
        instance_id=f"{settings.APP_NAME}-{settings.APP_ENV}",
    )
