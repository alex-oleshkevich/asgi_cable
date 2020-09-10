import typing as t

from django.urls import path, resolve

from ...websockets import WebSocket


def websockets(app: t.Callable):
    async def asgi(scope, receive, send):
        if scope["type"] == "websocket":
            match = resolve(scope["raw_path"])
            await match.func(
                WebSocket(scope, receive, send), *match.args, **match.kwargs
            )
            return
        await app(scope, receive, send)

    return asgi


websocket = path
