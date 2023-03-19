Build the image:

`docker build -t aob-example-express:1.0 .`

Run the image:

`docker run --init -p 3000:3000 aob-example-express:1.0 node app.js lmao`

The first port is the host's port and the second port is the container's port.
