const DEFAULT_INTERVALS = [10, 50, 100, 150, 200, 250, 500, 1000, 2000, 5000, 10000];
const DEFAULT_TIMEOUT = 10000;
const SERVICE_CHANNEL = '__service__';
const CHANNEL_EVENTS = {
    join: '__join__',
    reply: '__reply__',
    heartbeat: '__heartbeat__',
};

function makeReplyEventName(ref) {
    return `channel_reply_${ref}`;
}

class Push2 {
    /**
     *
     * @param {Channel} channel
     * @param {string} topic
     * @param {string} event
     * @param {string|Object|number} payload
     * @param {number} timeout
     */
    constructor(channel, topic, event, payload, timeout) {
        this.channel = channel;
        this.topic = topic;
        this.event = event;
        this.payload = payload;
        this.timeout = timeout;
        this.ref = channel.socket.nextRef();
        this.replyCallbacks = [];

        //
        this.timeoutTimer = null;
        this._promise = { resolve: null, reject: null };
    }

    async send() {
        return new Promise((resolve, reject) => {
            // store for later use
            this._promise = { resolve, reject };
            this.startTimeout();
            this.channel.socket.send({
                topic: this.topic,
                event: this.event,
                payload: this.payload || {},
                ref: this.ref,
            });
            this.on('ok', resolve);
            this.on('error', reject);
            this.on('timeout', reject);
        });
    }

    startTimeout() {
        this.ref = this.channel.socket.nextRef();
        this.timeoutTimer = setTimeout(() => {
            this.cancelTimeout();
            this.callReplyHooks(
                'timeout',
                `Timeout. Push did not receive a reply from socket after ${this.timeout}ms.`,
            );
        }, this.timeout);

        let replyEventName = makeReplyEventName(this.ref);
        this.channel.on(replyEventName, ({ status, response }, ref) => {
            this.callReplyHooks(status, response);
            this.cancelTimeout();
        });
    }

    cancelTimeout() {
        clearTimeout(this.timeoutTimer);
        this.timeoutTimer = null;
        let replyEventName = makeReplyEventName(this.ref);
        this.channel.off(replyEventName);
    }

    callReplyHooks(status, response) {
        this.replyCallbacks
            .filter(bind => bind.status === status)
            .forEach(bind => bind.fn(response));
    }

    on(status, fn) {
        this.replyCallbacks.push({ status: status, fn: fn });
    }

}


class Channel2 {

    /**
     *
     * @param {string} topic
     * @param {Socket} socket
     * @param {number} timeout
     */
    constructor(topic, socket, timeout) {
        this.topic = topic;
        this.socket = socket;
        this.listeners = {};
        this.timeout = timeout;

        // common event listeners
        this.on(CHANNEL_EVENTS.reply, (payload, ref) => {
            let replyEventName = makeReplyEventName(ref);
            this.trigger(replyEventName, payload, ref);
        });
    }

    join() {
        return this.send(CHANNEL_EVENTS.join);
    }

    leave() {
        return this.send(CHANNEL_EVENTS.leave);
    }

    send(event, payload) {
        return new Push(this, this.topic, event, payload, this.timeout).send();
    }

    on(event, fn) {
        let listeners = this.listeners[event] || [];
        listeners.push(fn);
        this.listeners[event] = listeners;
    }

    off(event, fn = null) {
        if (fn) {
            let listeners = this.listeners[event] || [];
            listeners = listeners.filter(listener => listener !== fn);
            this.listeners[event] = listeners;
        } else {
            this.listeners[event] = [];
        }
    }

    trigger(event, payload, ref) {
        let listeners = this.listeners[event] || [];
        listeners.forEach(fn => fn(payload, ref));
    }
}

const noop = () => {
};

class Socket2 {
    constructor(path, opts) {
        opts = opts || {};
        this.path = path;
        this.params = opts;
        this.timeout = opts.timeout || DEFAULT_TIMEOUT;
        this.heartbeatInterval = opts.heartbeatInterval || 30_000;
        this.reconnectIntervals = opts.reconnectIntervals || DEFAULT_INTERVALS;
        this.logger = opts.logger || noop;
        this.callbacks = { open: [], message: [], close: [], error: [] };
        this.reconnectTimer = new Timer(() => {
            this.teardown(() => this.connect());
        }, this.reconnectIntervals);

        // runtime
        this.channels = {};
        this.closeWasClean = false;
        this.refCounter = 0;
        this.heartbeatTimer = null;
    }

    get host() {
        return location.host;
    }

    get protocol() {
        return location.protocol.match(/^https/) ? 'wss' : 'ws';
    }

    get endpointUrl() {
        if (this.path.charAt(0) === '/') {
            return `${this.protocol}://${this.host}${this.path}`;
        }
        return this.path;
    }

    async connect() {
        return new Promise((resolve, reject) => {
            this.closeWasClean = false;
            this._socket = new WebSocket(this.endpointUrl);
            this._socket.onmessage = e => this.onSocketMessage(e);
            this._socket.onclose = e => this.onSocketClose(e);
            this._socket.onopen = e => {
                this.onSocketOpen(e);
                resolve(e);
            };
            this._socket.onerror = e => {
                this.onSocketError(e);
                reject(e);
            };
        });
    }

    disconnect(callback, code, reason) {
        this.closeWasClean = true;
        this.reconnectTimer.reset();
        this.teardown(callback, code, reason);
    }

    teardown(callback, code, reason) {
        this._socket.close(code, reason);
        callback && callback();
    }

    resetHeartbeat() {
        clearInterval(this.heartbeatTimer);
        this.heartbeatTimer = setInterval(() => {
            this.heartbeat();
        }, this.heartbeatInterval);
    }

    heartbeat() {
        this.send({
            topic: SERVICE_CHANNEL,
            event: CHANNEL_EVENTS.heartbeat,
            payload: {},
            ref: this.nextRef(),
        });
    }

    channel(topic) {
        this.channels[topic] = this.channels[topic] || [];

        let channel = new Channel(topic, this, this.timeout);
        this.channels[topic].push(channel);
        return channel;
    }

    /**
     *
     * @param {Event} e
     */
    onSocketOpen(e) {
        this.log(`Connected to ${this.endpointUrl}`);
        this.closeWasClean = false;
        this.reconnectTimer.reset();
        this.callbacks.open.forEach(fn => fn(e));
        this.resetHeartbeat();
    }

    /**
     *
     * @param {Event} e
     */
    onSocketError(e) {
        this.log(`Cannot connect to socket. Offline?`);
        this.callbacks.error.forEach(fn => fn(e));
    }

    /**
     *
     * @param {MessageEvent} e
     */
    onSocketMessage(e) {
        let data = JSON.parse(e.data);
        this.log('Received messages via socket: ', data);
        this.callbacks.message.forEach(fn => fn(data));

        let channels = this.channels[data.topic] || [];
        console.log(e.data);
        channels.forEach(channel => {
            channel.trigger(data.event, data.payload, data.ref);
        });
    }

    /**
     *
     * @param {CloseEvent} e
     */
    onSocketClose(e) {
        clearInterval(this.heartbeatTimer);
        if (!this.closeWasClean) {
            this.log(`Socket was abnormally closed. Scheduling reconnection.`);
            this.reconnectTimer.start();
        }
    }

    onOpen(fn) {
        this.callbacks.open.push(fn);
    }

    onClose(fn) {
        this.callbacks.close.push(fn);
    }

    onError(fn) {
        this.callbacks.error.push(fn);
    }

    onMessage(fn) {
        this.callbacks.message.push(fn);
    }

    send(message) {
        this._socket.send(JSON.stringify(message));
    }

    log(message, ...args) {
        if (this.logger) {
            this.logger(message, ...args);
        }
    }

    close(code = null, reason = null) {
        this._socket.close(code, reason);
    }

    nextRef() {
        this.refCounter++;
        return this.refCounter;
    }
}

class Timer2 {
    constructor(callback, intervals = null) {
        this._callback = callback;
        this._timer = null;
        this._tries = 0;
        this._intervals = intervals || [10, 50, 100, 150, 200, 250, 500, 1000, 2000, 5000, 10000];
    }

    reset() {
        this._tries = 0;
        clearTimeout(this._timer);
    }

    start() {
        clearTimeout(this._timer);
        this._timer = setTimeout(() => {
            this._tries = this._tries + 1;
            this._callback();
        }, this.nextInterval(this._tries + 1));
    }

    nextInterval(retry) {
        return this._intervals[retry - 1] || 10000;
    }
}

/** -------------------------------------------------------------------- **/

class Timer {
    constructor(fn, intervals) {
        this.fn = fn;
        this.intervals = intervals;
        this.retry = 0;
        this._timer = null;
    }

    start() {
        clearTimeout(this._timer);
        this._timer = setTimeout(() => {
            this.retry += 1;
            this.fn();
        }, this.nextInterval());
    }

    reset() {
        this.retry = 0;
        clearTimeout(this._timer);
    }

    nextInterval() {
        console.log('interval', this.intervals[this.retry] || 10000);
        return this.intervals[this.retry] || 10000;
    }
}

const defaultOptions = {
    reconnectIntervals: DEFAULT_INTERVALS,
};

/**
 * @property {WebSocket} _socket
 */
class Socket {
    constructor(path, options = defaultOptions) {
        if (path.charAt(0) === '/') {
            let protocol = location.protocol === 'https' ? 'wss' : 'ws';
            let host = location.host;
            path = `${protocol}://${host}${path}`;
        }
        this.url = path;
        this._socket = null;
        this._subscribers = {
            open: [],
            message: [],
            error: [],
            close: [],
        };
        this.reconnectTimer = new Timer(() => this.connect(), options.reconnectIntervals);
        this.on('open', () => {
            this.reconnectTimer.reset();
        });
        this.on('close', event => {
            this.onErrorClose(event);
        });
    }

    connect() {
        return new Promise((resolve, reject) => {
            this.closeWasClean = true;
            this._socket = new WebSocket(this.url);
            this._socket.onopen = event => {
                this.dispatch('open', event);
                resolve(event);
            };
            this._socket.onmessage = event => this.dispatch('message', event);
            this._socket.onerror = event => event => {
                this.dispatch('error', event);
                reject(event);
            };
            this._socket.onclose = event => this.dispatch('close', event);
        });
    }

    disconnect(code, reason) {
        return this.teardown(code, reason);
    }

    dispatch(type, event) {
        this._subscribers[type].forEach(fn => fn(event));
    }

    on(event, fn) {
        if (!(event in this._subscribers)) {
            throw new Error(`Event "${event}" is not available for subscription.`);
        }
        this._subscribers[event].push(fn);
    }

    off(event, fn) {
        if (!(event in this._subscribers)) {
            throw new Error(`Event "${event}" is not available for subscription.`);
        }
        this._subscribers[event] = this._subscribers[event].filter(cb => cb !== fn);
    }

    send(data) {
        return this._socket.send(JSON.stringify(data));
    }

    teardown(code, reason) {
        return new Promise((resolve, reject) => {
            this._socket.close(code, reason);
            resolve();
        });
    }

    /**
     * @param {CloseEvent} event
     */
    onErrorClose(event) {
        if (event.wasClean) {
            return;
        }
        this.reconnectTimer.start();
    }
}
