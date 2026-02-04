"""
\U0001F4E5 Async Streaming Support Across Bots
\U0001F9E0 Best Practices: Chunked context ingestion, bidirectional task I/O, transformer/agent loop compatibility

This module provides a streaming handler that accepts incremental JSON packets
and routes them through any bot function that supports a coroutine-based stream interface.
"""

from __future__ import annotations

from typing import AsyncIterable, Awaitable, Callable, Dict, Any
import asyncio
import json


class StreamingInputHandler:
    """Route streaming JSON data to coroutine handlers."""

    def __init__(self) -> None:
        self.registered_endpoints: Dict[str, Callable[[AsyncIterable[Dict[str, Any]]], Awaitable[Any]]] = {}

    def register(self, route: str, handler: Callable[[AsyncIterable[Dict[str, Any]]], Awaitable[Any]]) -> None:
        """Register a stream handler."""
        self.registered_endpoints[route] = handler

    async def stream_from_request(self, route: str, stream: AsyncIterable[bytes]) -> Any:
        """Decode JSON chunks from *stream* and dispatch to the handler for *route*."""
        if route not in self.registered_endpoints:
            raise ValueError(f"No handler registered for: {route}")

        async def decoded_chunks() -> AsyncIterable[Dict[str, Any]]:
            async for chunk in stream:
                try:
                    yield json.loads(chunk)
                except Exception as exc:  # pragma: no cover - error path
                    yield {"error": str(exc)}

        return await self.registered_endpoints[route](decoded_chunks())


async def async_json_echo(input_stream: AsyncIterable[Dict[str, Any]]) -> list:
    """Example consumer that echoes JSON objects from the stream."""
    output = []
    async for obj in input_stream:
        output.append(obj)
    return output


async def demo() -> None:  # pragma: no cover - manual usage
    handler = StreamingInputHandler()
    handler.register("/echo", async_json_echo)

    async def mock_stream() -> AsyncIterable[bytes]:
        for item in [b'{"msg": "one"}', b'{"msg": "two"}']:
            yield item
            await asyncio.sleep(0.05)

    result = await handler.stream_from_request("/echo", mock_stream())
    print(result)


if __name__ == "__main__":  # pragma: no cover - manual execution
    asyncio.run(demo())
