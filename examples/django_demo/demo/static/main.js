async function main() {
    let socket = new Socket('/ws/');
    await socket.connect()
}

main();

