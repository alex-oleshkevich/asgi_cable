// let echoSocket = new Socket('/ws/');
// setInterval(() => {
//     echoSocket.send({'message': 'Hello'});
// }, 1000);
// echoSocket.on('message', console.log);
// echoSocket.connect();

let socket = new Socket('/channels/');
socket.on('open', () => console.log('socket connection open'));
socket.on('message', () => console.log('socket received message'));
socket.on('error', () => console.log('socket got an error'));
socket.on('close', () => console.log('socket connection closed'));

socket.connect().then(() => {
    let channel = socket.channel('room:lobby');
    channel.join().then(() => {
        console.log('Channel joined.');
    }).catch(e => console.error);
});
