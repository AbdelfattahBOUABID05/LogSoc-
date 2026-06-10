# Use Node 18 Alpine as requested
FROM node:18-alpine
WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source files
COPY . .

# Expose the Angular development port
EXPOSE 4200

# Start the application in development mode
# We use --host 0.0.0.0 to allow access from outside the container
CMD ["npm", "start", "--", "--host", "0.0.0.0", "--port", "4200", "--disable-host-check"]
