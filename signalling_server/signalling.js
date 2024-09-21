const WebSocket = require("ws");
const { v4: uuidv4 } = require("uuid"); // To generate unique IDs
const express = require("express");
const cors = require("cors");
const path = require("path");
const http = require("http");

const app = express();
const server = http.createServer(app);

app.use(cors());
app.use(express.static(path.join(__dirname, "src")));
app.set("views", path.join(__dirname, "views"));
app.set("view engine", "ejs");
app.use(express.urlencoded({ extended: true }));

const port = 9000;
// Create a WebSocket server
const wss = new WebSocket.Server({ server });

app.get("/join", (req, res) => {
  res.render("join");
});

app.post("/select-camera", (req, res) => {
  var roomId = req.body.roomId;
  const username = req.body.username;
  const age = req.body.age;
  const gender = req.body.gender;

  if (!roomId) {
    roomId = req.body.genRoomId;
  }

  res.render("select_camera", {
    roomId: roomId,

    username: username,
    age: age,
    gender: gender,
  });
});

app.get("/room", (req, res) => {
  const leftDeviceId = req.query.leftDevice;
  const rightDeviceId = req.query.rightDevice;
  const roomId = req.query.roomId;
  const username = req.query.username;
  const age = req.query.age;
  const gender = req.query.gender;

  res.render("room", {
    roomId: roomId,
    username: username,
    age: age,
    gender: gender,
    leftDeviceId: leftDeviceId,
    rightDeviceId: rightDeviceId,
  });
});

// Create an object to store the rooms and their associated clients
const rooms = {};

// Handle new WebSocket connections
wss.on("connection", (ws) => {
  console.log("New client connected");

  // Assign a room to the client (the client should send a message specifying the room)
  ws.on("message", (message) => {
    try {
      const data = JSON.parse(message); // Attempt to parse JSON

      // New user is joining the room
      if (data.type === "join") {
        const clientId = uuidv4();
        const room = data.room;

        if (!rooms[room]) {
          rooms[room] = []; // Create room if it doesn't exist
        }

        rooms[room].push({ wsClient: ws, userId: clientId }); // Add client to the room
        ws.room = room; // Track which room the client belongs to
        ws.userId = clientId; // Assign the userId to the WebSocket client

        const randomNumber = Math.floor(Math.random() * 10) + 1;

        ws.send(
          JSON.stringify({
            userId: clientId,
            roomId: room,
            username: data.username,
            gender: data.gender,
            age: data.age,
            productivityScore: randomNumber,
          })
        );

        console.log(
          `Client joined room: ${room}, Name: ${data.name}, ID: ${clientId}`
        );
      }

      // Broadcast a message to everyone in the room except the sender
      if (data.type === "broadcast") {
        const room = data.room;

        if (rooms[room]) {
          rooms[room].forEach((client) => {
            if (
              client.wsClient !== ws &&
              client.wsClient.readyState === WebSocket.OPEN
            ) {
              console.log("offer received on server", ws.userId);
              if (data.msgType === "offer") {
                client.wsClient.send(
                  JSON.stringify({
                    msgType: "offer",
                    msg: data.msg,
                    roomId: room,
                    userId: ws.userId,
                  })
                );
              }

              if (data.msgType === "candidate") {
                console.log("candidate received on server", ws.userId);
                client.wsClient.send(
                  JSON.stringify({
                    msgType: "candidate",
                    roomId: room,
                    candidate: data.candidate,
                    sdpmid: data.sdpmid,
                    sdpmlineindex: data.sdpmlineindex,
                    userId: ws.userId,
                  })
                );
              }

              if (data.msgType === "answer") {
                console.log("answer received on server", ws.userId);
                client.wsClient.send(
                  JSON.stringify({
                    msgType: "answer",
                    msg: data.msg,
                    roomId: room,
                    userId: ws.userId,
                  })
                );
              }
            }
          });
        }
      }
    } catch (error) {
      console.error("Error parsing JSON:", error.message); // Handle any errors
    }
  });

  // Handle client disconnect
  ws.on("close", () => {
    const room = ws.room;
    if (room && rooms[room]) {
      rooms[room] = rooms[room].filter((client) => client.wsClient !== ws); // Remove client from room
      if (rooms[room].length === 0) {
        delete rooms[room]; // Delete room if empty
      }
      console.log(`Client disconnected from room: ${ws.userId}`);
    }
  });
});

server.listen(port, () => {
  console.log("server is running on port", port);
});
