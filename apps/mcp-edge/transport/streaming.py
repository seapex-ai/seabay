"""Streaming HTTP transport with SSE for real-time MCP responses.

Implements the MCP streaming transport specification:
- Streaming HTTP as primary transport
- SSE (Server-Sent Events) for backward compatibility
- Keepalive heartbeats to maintain connections

Per MCP spec, the transport layer is protocol-neutral. Tool dispatch
happens at the endpoint level; this module handles framing and delivery.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from config import settings

logger = logging.getLogger("mcp-edge.transport")

router = APIRouter()


async def _sse_event_stream(
    event_type: str,
    data: dict,
    keepalive: bool = True,
) -> AsyncGenerator[str, None]:
    """Generate SSE event stream with optional keepalive.

    Yields SSE-formatted events: "event: {type}\ndata: {json}\n\n"
    """
    # Send the main event
    yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    # Keepalive loop (for long-running tool executions)
    if keepalive:
        try:
            while True:
                await asyncio.sleep(settings.SSE_KEEPALIVE_INTERVAL)
                yield f"event: keepalive\ndata: {json.dumps({'ts': int(time.time())})}\n\n"
        except asyncio.CancelledError:
            # Client disconnected
            yield f"event: done\ndata: {json.dumps({'status': 'disconnected'})}\n\n"


@router.get("/sse/stream")
async def sse_stream(request: Request):
    """SSE endpoint for real-time event streaming.

    Clients connect to this endpoint to receive server-sent events.
    Used for long-running tool executions and task status updates.

    Events:
    - tool_result: Result of a tool invocation
    - task_update: Task status change notification
    - keepalive: Periodic heartbeat to maintain connection
    - done: Stream is complete
    """

    async def _stream() -> AsyncGenerator[str, None]:
        """Generate initial connection event and keepalive heartbeats."""
        # Connection established event
        yield f"event: connected\ndata: {json.dumps({'version': settings.APP_VERSION, 'transport': 'sse'})}\n\n"

        # Keepalive loop
        try:
            while True:
                await asyncio.sleep(settings.SSE_KEEPALIVE_INTERVAL)
                if await request.is_disconnected():
                    break
                yield f"event: keepalive\ndata: {json.dumps({'ts': int(time.time())})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            yield f"event: done\ndata: {json.dumps({'status': 'closed'})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sse/invoke")
async def sse_invoke(request: Request):
    """Streaming HTTP endpoint for tool invocation with SSE response.

    Accepts a tool invocation request and streams the response as SSE events.
    This is the primary transport for MCP hosts that support streaming HTTP.

    Request body:
    {
        "tool": "search_agents",
        "arguments": {...}
    }

    Response: SSE stream with tool_result event.
    """
    body = await request.json()
    tool_name = body.get("tool", "")
    body.get("arguments", {})

    async def _invoke_stream() -> AsyncGenerator[str, None]:
        # Emit processing event
        yield f"event: processing\ndata: {json.dumps({'tool': tool_name, 'status': 'started'})}\n\n"

        # Dispatch to the appropriate tool handler
        # (In production, this would dynamically route to tool handlers)
        result = {
            "tool": tool_name,
            "status": "completed",
            "message": f"Tool '{tool_name}' invoked via streaming transport. "
                       "Use the /tools/{tool_name} endpoint for direct invocation.",
        }

        yield f"event: tool_result\ndata: {json.dumps(result)}\n\n"
        yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"

    return StreamingResponse(
        _invoke_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/messages")
async def streaming_http_messages(request: Request):
    """Streamable HTTP transport endpoint (MCP 2025-03 spec).

    Handles JSON-RPC style messages over streaming HTTP.
    This is the newer transport format preferred by Claude.

    Request body: JSON-RPC 2.0 message
    Response: JSON-RPC 2.0 response (may be streamed)
    """
    body = await request.json()
    method = body.get("method", "")
    params = body.get("params", {})
    msg_id = body.get("id")

    # Handle MCP protocol methods
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "Seabay",
                    "version": settings.APP_VERSION,
                },
            },
        }

    elif method == "tools/list":
        # Import tool schemas
        from tools.search_agents import TOOL_SCHEMA as search_schema
        from tools.get_agent_profile import TOOL_SCHEMA as profile_schema
        from tools.create_task import TOOL_SCHEMA as create_task_schema
        from tools.get_task import TOOL_SCHEMA as get_task_schema
        from tools.list_inbox import TOOL_SCHEMA as list_inbox_schema
        from tools.confirm_human import TOOL_SCHEMA as confirm_schema

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    search_schema,
                    profile_schema,
                    create_task_schema,
                    get_task_schema,
                    list_inbox_schema,
                    confirm_schema,
                ],
            },
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        params.get("arguments", {})

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Tool '{tool_name}' invoked. "
                            "Use the /tools/{tool_name} REST endpoint for full execution."
                        ),
                    }
                ],
                "isError": False,
            },
        }

    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }
