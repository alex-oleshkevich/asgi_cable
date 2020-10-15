from __future__ import annotations

import asyncio
import dataclasses
import datetime
import re
import typing as t

from .websockets import WebSocket


class ServiceEvents:
    JOIN = '__join__'
    LEAVE = '__leave__'
    HEARTBEAT = '__heartbeat__'
    REPLY = '__reply__'


class ReplyStatus:
    OK = 'ok'
    ERROR = 'error'


@dataclasses.dataclass
class Event:
    topic: str
    name: str
    ref: int
    websocket: WebSocket = None

    async def reply(self, data: t.Any = None, success: bool=True):
        await self.websocket.send_json({
            'topic': self.topic,
            'event': ServiceEvents.REPLY,
            'data': {
                'status': ReplyStatus.OK if success else ReplyStatus.ERROR,
                'data': data,
            },
            'ref': self.ref,
        })

    def to_json(self) -> t.Dict:
        return dict(
            topic=self.topic,
            name=self.name,
            ref=self.ref,
        )


class ChannelError(Exception): ...


class AuthorizationError(ChannelError):
    pass


class Backend:
    async def add(self, channel: Channel):
        raise NotImplementedError()

    async def remove(self, channel: Channel):
        raise NotImplementedError()

    async def publish(self, channel: Channel, event: Event):
        raise NotImplementedError()

    async def subscribe(self, topic: str):
        raise NotImplementedError()


class InMemoryBackend(Backend):
    def __init__(self):
        self._channels: t.Dict[str, t.List[Channel]] = {}
        self._queue = asyncio.Queue()

    async def add(self, channel: Channel):
        self._channels.setdefault(channel.name, [])
        self._channels[channel.name].append(channel)

    async def remove(self, channel: Channel):
        self._channels[channel.name].remove(channel)

    async def publish(self, channel: Channel, event: Event):
        await asyncio.gather([
            self._queue.put(event) for channel in self._channels[channel.name]
        ])


class Channel:
    def __init__(self, name: str, websocket: WebSocket, backend: Backend):
        self.name = name
        self.websocket = websocket
        self._backend = backend

    async def dispatch(self, event: Event):
        if event.name == ServiceEvents.JOIN:
            await self.join(event)
        elif event.name == ServiceEvents.LEAVE:
            await self.leave()
        else:
            await self.received(event)

    async def join(self, event: Event):
        try:
            authorized = await self.authorize(self.websocket.scope)
            if not authorized:
                raise AuthorizationError('Not authorized to join.')
            await self._backend.add(self)
            await self.joined()
        except AuthorizationError as ex:
            await event.reply(ReplyStatus.ERROR, str(ex))
        else:
            await event.reply(ReplyStatus.OK, 'Successfully joined channel.')

    async def joined(self):
        ...

    async def authorize(self, scope: t.Dict) -> bool:
        return True

    async def leave(self):
        await self._backend.remove(self)
        await self.left()

    async def left(self):
        ...

    async def received(self, event: Event):
        pass


class Socket:
    channels: t.Dict[str, t.Type[Channel]] = None

    def __init__(self, backend: Backend):
        self._backend = backend

    async def __call__(self, websocket: WebSocket):
        await websocket.accept()
        while True:
            data = await websocket.receive_json()
            assert data['topic'], 'Every event must define "topic" key.'
            assert data['event'], 'Every event must define "name" key.'
            event = Event(
                topic=data['topic'],
                name=data['event'],
                ref=data['ref'],
                websocket=websocket,
            )
            for pattern, channel_class in self.channels.items():
                if re.match(pattern, event.topic):
                    channel = channel_class(
                        event.topic, websocket, self._backend,
                    )
                    await channel.dispatch(event)
