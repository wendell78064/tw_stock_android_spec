import asyncio
import json
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.core.dependencies import get_realtime_cache_service, get_realtime_hub, get_realtime_provider_manager
from app.domain.realtime import ProviderCapabilities, RealtimeQuote
from app.services.realtime_cache import RealtimeCacheService
from app.services.realtime_hub import RealtimeQuoteHub
from app.services.realtime_provider_manager import RealtimeProviderManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Realtime Quotes"])


class SecurityTargetInput(BaseModel):
    code: str
    market: str


class BatchQuoteRequestInput(BaseModel):
    targets: list[SecurityTargetInput] = Field(..., max_length=100)


class RealtimeHealthResponse(BaseModel):
    provider_connected: bool
    provider_status: str
    capabilities: ProviderCapabilities
    active_ws_connections: int
    active_subscriptions: int
    quotes_received: int
    quotes_published: int
    quotes_coalesced: int
    reconnect_count: int


@router.get("/quotes/health", response_model=RealtimeHealthResponse)
async def get_realtime_health(
    manager: Annotated[RealtimeProviderManager, Depends(get_realtime_provider_manager)],
    hub: Annotated[RealtimeQuoteHub, Depends(get_realtime_hub)],
) -> RealtimeHealthResponse:
    capabilities = await manager.get_capabilities()
    healthy = await manager.provider.health()
    active_subs = sum(len(s.subscriptions) for s in hub.sessions)

    return RealtimeHealthResponse(
        provider_connected=healthy,
        provider_status=hub.provider_status,
        capabilities=capabilities,
        active_ws_connections=len(hub.sessions),
        active_subscriptions=active_subs,
        quotes_received=hub.quotes_received,
        quotes_published=hub.quotes_published,
        quotes_coalesced=hub.quotes_coalesced,
        reconnect_count=manager.reconnect_count,
    )


@router.get("/quotes/{market}/{code}", response_model=RealtimeQuote)
async def get_latest_quote(
    market: str,
    code: str,
    cache_service: Annotated[RealtimeCacheService, Depends(get_realtime_cache_service)],
) -> RealtimeQuote:
    quote = await cache_service.get_quote(market, code)
    if not quote:
        raise HTTPException(status_code=404, detail=f"No realtime quote cached for {market}:{code}")
    return quote


@router.post("/quotes/batch", response_model=list[RealtimeQuote | None])
async def get_quotes_batch(
    payload: BatchQuoteRequestInput,
    cache_service: Annotated[RealtimeCacheService, Depends(get_realtime_cache_service)],
) -> list[RealtimeQuote | None]:
    targets = [{"market": t.market, "code": t.code} for t in payload.targets]
    return await cache_service.get_quotes_batch(targets)


@router.websocket("/ws/quotes")
async def websocket_quotes_endpoint(
    websocket: WebSocket,
    hub: Annotated[RealtimeQuoteHub, Depends(get_realtime_hub)],
):
    await websocket.accept()
    session = await hub.register_connection(websocket)

    try:
        # Welcome message
        await websocket.send_json(
            {
                "type": "status",
                "version": 1,
                "status": hub.provider_status,
                "message": "Connected to Realtime Quote Stream",
            }
        )

        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                msg_type = msg.get("type")
                version = msg.get("version", 1)

                if msg_type == "subscribe":
                    targets = msg.get("securities", [])
                    await hub.handle_subscribe(session, targets)
                    await websocket.send_json(
                        {
                            "type": "status",
                            "version": version,
                            "message": f"Subscribed to {len(targets)} securities",
                        }
                    )
                elif msg_type == "unsubscribe":
                    targets = msg.get("securities", [])
                    await hub.handle_unsubscribe(session, targets)
                    await websocket.send_json(
                        {
                            "type": "status",
                            "version": version,
                            "message": f"Unsubscribed from {len(targets)} securities",
                        }
                    )
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong", "version": version})
                else:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "version": version,
                            "message": f"Unknown message type: {msg_type}",
                        }
                    )
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"type": "error", "version": 1, "message": "Invalid JSON format"}
                )
    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    finally:
        await hub.unregister_connection(session)
