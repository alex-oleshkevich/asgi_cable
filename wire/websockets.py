import json
import typing as t
from urllib import parse


class State:
    CONNECTING = 1
    CONNECTED = 2
    DISCONNECTED = 3


class SendEvent:
    """Lists events that application can send.

    ACCEPT - Sent by the application when it wishes to accept an incoming connection.
    SEND - Sent by the application to send a data message to the client.
    CLOSE - Sent by the application to tell the server to close the connection.
        If this is sent before the socket is accepted, the server must close
        the connection with a HTTP 403 error code (Forbidden), and not complete
        the WebSocket handshake; this may present on some browsers as
        a different WebSocket error code (such as 1006, Abnormal Closure).
    """

    ACCEPT = "websocket.accept"
    SEND = "websocket.send"
    CLOSE = "websocket.close"


class ReceiveEvent:
    """Enumerates events that application can receive from protocol server.

    CONNECT - Sent to the application when the client initially
        opens  a connection and is about to finish the WebSocket handshake.
        This message must be responded to with either an Accept message or a Close message
        before the socket will pass websocket.receive messages.
    RECEIVE - Sent to the application when a data message is received from the client.
    DISCONNECT - Sent to the application when either connection to the client is lost,
        either from the client closing the connection,
        the server closing the connection, or loss of the socket.
    """

    CONNECT = "websocket.connect"
    RECEIVE = "websocket.receive"
    DISCONNECT = "websocket.disconnect"


class Headers:
    def __init__(self, scope):
        self._scope = scope

    def keys(self):
        return [header[0].decode() for header in self._scope["headers"]]

    def as_dict(self) -> dict:
        return {h[0].decode(): h[1].decode() for h in self._scope["headers"]}

    def __getitem__(self, item: str) -> str:
        return self.as_dict()[item.lower()]

    def __repr__(self) -> str:
        return str(dict(self))


class QueryParams:
    def __init__(self, query_string: str):
        self._dict = dict(parse.parse_qsl(query_string))

    def keys(self):
        return self._dict.keys()

    def get(self, item, default=None):
        return self._dict.get(item, default)

    def __getitem__(self, item: str):
        return self._dict[item]

    def __repr__(self) -> str:
        return str(dict(self))


class WebSocket:
    def __init__(self, scope, receive, send):
        self._scope = scope
        self._receive = receive
        self._send = send
        self._client_state = State.CONNECTING
        self._app_state = State.CONNECTING

    @property
    def headers(self):
        return Headers(self._scope)

    @property
    def scheme(self):
        return self._scope["scheme"]

    @property
    def path(self):
        return self._scope["path"]

    @property
    def query_params(self):
        return QueryParams(self._scope["query_string"].decode())

    @property
    def query_string(self) -> str:
        return self._scope["query_string"]

    @property
    def scope(self):
        return self._scope

    async def accept(self, subprotocol: str = None):
        """Accept connection.

        :param subprotocol: The subprotocol the server wishes to accept.
        :type subprotocol: str, optional
        """
        if self._client_state == State.CONNECTING:
            await self.receive()
        await self.send({"type": SendEvent.ACCEPT, "subprotocol": subprotocol})

    async def close(self, code: int = 1000):
        await self.send({"type": SendEvent.CLOSE, "code": code})

    async def send(self, message: t.Mapping):
        if self._app_state == State.DISCONNECTED:
            raise RuntimeError("WebSocket is disconnected.")

        if self._app_state == State.CONNECTING:
            assert message["type"] in {SendEvent.ACCEPT, SendEvent.CLOSE}, (
                'Could not write event "%s" into socket in connecting state.'
                % message["type"]
            )
            if message["type"] == SendEvent.CLOSE:
                self._app_state = State.DISCONNECTED
            else:
                self._app_state = State.CONNECTED

        elif self._app_state == State.CONNECTED:
            assert message["type"] in {SendEvent.SEND, SendEvent.CLOSE}, (
                'Connected socket can send "%s" and "%s" events, not "%s"'
                % (SendEvent.SEND, SendEvent.CLOSE, message["type"])
            )
            if message["type"] == SendEvent.CLOSE:
                self._app_state = State.DISCONNECTED

        await self._send(message)

    async def receive(self):
        if self._client_state == State.DISCONNECTED:
            raise RuntimeError("WebSocket is disconnected.")

        message = await self._receive()

        if self._client_state == State.CONNECTING:
            assert message["type"] == ReceiveEvent.CONNECT, (
                'WebSocket is in connecting state but received "%s" event'
                % message["type"]
            )
            self._client_state = State.CONNECTED

        elif self._client_state == State.CONNECTED:
            assert message["type"] in {ReceiveEvent.RECEIVE, ReceiveEvent.DISCONNECT}, (
                'WebSocket is connected but received invalid event "%s".'
                % message["type"]
            )
            if message["type"] == ReceiveEvent.DISCONNECT:
                self._client_state = State.DISCONNECTED

        return message

    async def receive_json(self) -> t.Any:
        message = await self.receive()
        self._test_if_can_receive(message)
        return json.loads(message["text"])

    async def receive_jsonb(self) -> t.Any:
        message = await self.receive()
        self._test_if_can_receive(message)
        return json.loads(message["bytes"].decode())

    async def receive_text(self) -> str:
        message = await self.receive()
        self._test_if_can_receive(message)
        return message["text"]

    async def receive_bytes(self) -> bytes:
        message = await self.receive()
        self._test_if_can_receive(message)
        return message["bytes"]

    async def send_json(self, data: t.Any, **dump_kwargs):
        data = json.dumps(data, **dump_kwargs)
        await self.send({"type": SendEvent.SEND, "text": data})

    async def send_jsonb(self, data: t.Any, **dump_kwargs):
        data = json.dumps(data, **dump_kwargs)
        await self.send({"type": SendEvent.SEND, "bytes": data.encode()})

    async def send_text(self, text: str):
        await self.send({"type": SendEvent.SEND, "text": text})

    async def send_bytes(self, text: t.Union[str, bytes]):
        if isinstance(text, str):
            text = text.encode()
        await self.send({"type": SendEvent.SEND, "bytes": text})

    def _test_if_can_receive(self, message: t.Mapping):
        assert message["type"] == ReceiveEvent.RECEIVE, (
            'Invalid message type "%s". Was connection accepted?' % message["type"]
        )
        return True
