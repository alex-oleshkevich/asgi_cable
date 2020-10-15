import typing as t
from django.views.generic import TemplateView

from asgi_cable import WebSocket
from asgi_cable.channels import Channel, Event, Socket


class IndexView(TemplateView):
    template_name = 'index.html'


async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    while True:
        message = await websocket.receive_json()
        await websocket.send_json(message)


class ChatRoom(Channel):
    async def received(self, event: Event):
        if event.name == 'message':
            await event.reply('Accepted', True)

    # async def authorize(self, scope: t.Dict) -> bool:
    #     return False

class RoomSocket(Socket):
    channels = {
        'room:*': ChatRoom,
    }
