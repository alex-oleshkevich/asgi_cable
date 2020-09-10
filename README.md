# Wire - WebSocket framework for ASGI apps.

## Installation

```bash
pip install wire
# or
poetry add wire
```

## Usage

## Usage with django

TBD

```python
# urls.py
from wire.contrib.django import websocket
from wire import WebSocket

async def ws_handler(request: WebSocket):
    await request.accept()
    await request.send('Hello')
    await request.close()

urlpatterns = [
    # ...
    websocket('ws/', ws_handler),
]
```
