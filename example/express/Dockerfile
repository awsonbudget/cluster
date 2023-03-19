# Use an official Node.js runtime as a parent image
FROM node:18

# Set the working directory to /app
WORKDIR /app

# Copy everything to the working directory
COPY . .

# Install any dependencies
RUN npm install

# Expose port 3000 for the server to listen on
EXPOSE 3000