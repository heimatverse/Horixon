const express = require("express");
const { rmSync } = require("fs");
const path = require("path");
const app = express();
const server = require("http").createServer(app);
const io = require("socket.io")(server);
var cors = require("cors");
const PORT = 3000;

// server config ----------------------------------------->
app.use(cors());
app.use(express.static(path.join(__dirname, "public")));
app.set("views", path.join(__dirname, "views"));
app.set("view engine", "ejs");
app.use(express.urlencoded({ extended: true }));

// endpoints --------------------------->
app.get("/", (req, res, next) => {
  res.render("create");
});

app.post("/join", (req, res) => {
  const roomId = req.body.roomId;

  // adding roomId validation
  if (!roomId || !/^[A-Za-z0-9]{3,}$/.test(roomId)) {
    return res
      .status(400)
      .send(
        "Invalid Room ID. Room ID must be at least 3 characters long and contain only letters and numbers."
      );
  }

  res.redirect(`/room/${roomId}`);
});

app.get("/room/:roomId", (req, res) => {
  const roomId = req.params.roomId;

  // const users = [];

  // const sockets = io.sockets.adapter.rooms[roomId].sockets;

  // for (const key in sockets) {
  //   users.push(key);
  // }

  res.render("room", { roomId: roomId });
});

app.get("/get-rooms", (req, res) => {
  // Get all the currently made rooms
  const rooms = Object.keys(io.sockets.adapter.rooms);
  res.send(rooms);

  users = [];

  for (const key in sockets) {
    users.push(key);
  }
  console.log(users);
});

// socket logic ------------------------------------>
io.on("connection", (socket) => {
  console.log("a user connected via socket!");

  socket.on("joinRoom", (roomId, peerId) => {
    console.log("A user connected to the room", roomId, peerId);
    socket.join(roomId);
    socket.emit("msg", "to alll");
    io.to(roomId).emit("msg", peerId);
    socket.broadcast.to(roomId).emit("msg", peerId);
  });

  socket.on("disconnect", () => {
    console.log("a user disconnected!");
  });

  socket.on("chatMessage", (msg) => {
    console.log("Message: " + msg.message);
    io.emit("chatMessage", msg);
  });
});

server.listen(PORT, () => {
  console.log("Server listening on port " + PORT + "!");
});
