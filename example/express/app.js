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

function generateRandomString(length) {
  let result = "";
  const characters =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  for (let i = 0; i < length; i++) {
    result += characters.charAt(Math.floor(Math.random() * characters.length));
  }
  return result;
}

function sortRandomStrings(numStrings, stringLength) {
  const strings = [];
  for (let i = 0; i < numStrings; i++) {
    strings.push(generateRandomString(stringLength));
  }
  return strings.sort();
}

app.get("/sort/:numStrings/:stringLength", (req, res) => {
  const numStrings = parseInt(req.params.numStrings);
  const stringLength = parseInt(req.params.stringLength);
  const sortedStrings = sortRandomStrings(numStrings, stringLength);
  res.send(
    `Generated and sorted ${numStrings} strings of length ${stringLength}`
  );
});

app.listen(port, () => {
  console.log(`Example app listening on port ${port}`);
});
