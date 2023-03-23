const express = require("express");
const app = express();
const port = 3000;

let count = 1;
const argument = process.argv[2];

app.get("/", (req, res) => {
  const msg = `Hello World! From ${argument}. This is request #${count}`;
  res.send(msg);
  console.log(msg);
  count += 1;
});

app.get("/ping", (req, res) => {
  res.send("pong!");
});

function factorial(n) {
  if (n === 0) {
    return 1;
  }
  return n * factorial(n - 1);
}

app.get("/factorial/:n", (req, res) => {
  const n = parseInt(req.params.n);
  const result = factorial(n);
  res.send(`${argument}: The factorial of ${n} is ${result}`);
});

app.listen(port, () => {
  console.log(`Example app listening on port ${port}`);
});
