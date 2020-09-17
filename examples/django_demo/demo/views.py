from django.views.generic import TemplateView

from asgi_cable import WebSocket


class IndexView(TemplateView):
    template_name = 'index.html'


async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    while True:
        message = await websocket.receive_json()
        print(message)
        await websocket.send_json(message)
