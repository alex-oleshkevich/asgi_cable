let socket = new Socket('/channels/');
socket.onOpen(() => console.log('socket connection open'));
socket.onMessage(() => console.log('socket received message'));
socket.onError(() => console.log('socket got an error'));
socket.onClose(() => console.log('socket connection closed'));

async function main() {
    await socket.connect();
    let channel = socket.channel('room:lobby');
    try {
        let result = await channel.join();
        console.log(result);
    } catch (e) {
        console.log('Did not join the channel.', e);
    }
}

main();
