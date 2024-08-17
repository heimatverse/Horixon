import Peer from "peerjs";

// intializeing peer id
const peerId = "mukal";

var peer = new Peer();

var conn = peer.connect(peerId);

conn.on("open", function () {
  console.log("Connected!");
  conn.send("Hello, peer!");
});

peer.on("connection", function (conn) {
  conn.on("data", function (data) {
    console.log("Received message:", data);
  });
});
