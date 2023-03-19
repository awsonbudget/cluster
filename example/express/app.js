const express = require("express");
const app = express();
const port = 3000;

let count = 1;

app.get("/", (req, res) => {
  const argument = process.argv[2];
  const msg = `Hello World! From ${argument}. This is request #${count}`;
  res.send(msg);
  console.log(msg);
  count += 1;
});

app.get("/ping", (req, res) => {
  res.send("pong!");
});

app.listen(port, () => {
  console.log(`Example app listening on port ${port}`);
});
