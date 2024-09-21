# Use the official Node.js image from the Docker Hub
FROM node:16  

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy package.json and package-lock.json (if available)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of your application code
COPY . .

# Expose the port your app runs on (change this if your app uses a different port)
EXPOSE 9000

# Command to run your application
CMD ["node", "signalling.js"] 
    