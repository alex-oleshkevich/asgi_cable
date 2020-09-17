import typing as t

from django import apps
from django.urls import path, resolve

from ...websockets import WebSocket


def websockets(app: t.Callable):
    async def middleware(scope, receive, send):
        if scope["type"] == "websocket":
            match = resolve(scope["raw_path"])
            await match.func(
                WebSocket(scope, receive, send), *match.args, **match.kwargs
            )
            return
        await app(scope, receive, send)

    return middleware


websocket = path


class CableAppConfig(apps.AppConfig):
    pass
