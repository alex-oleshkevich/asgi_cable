# A framework for the real-time ASGI apps.

## Installation

```bash
pip install asgi_cable
# or
poetry add asgi_cable
```

## Usage

## Usage with django

TBD

```python
# urls.py
from asgi_cable.contrib.django import websocket
from asgi_cable import WebSocket

async def ws_handler(request: WebSocket):
    await request.accept()
    await request.send('Hello')
    await request.close()

urlpatterns = [
    # ...
    websocket('ws/', ws_handler),
]
```
