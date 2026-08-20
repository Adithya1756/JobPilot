# JobPilot Frontend - Production Dockerfile
FROM node:20-alpine

# Set environment
ENV NODE_ENV=production

# Create non-root user
RUN addgroup -g 1001 -S nextjs && adduser -S nextjs -u 1001

# Set working directory
WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci || npm install

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Change ownership
RUN chown -R nextjs:nextjs /app

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Start the production server
CMD ["npm", "start"]