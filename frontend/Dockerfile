# VERIDEX Frontend Container Configuration
FROM node:20-alpine as build

WORKDIR /app

# Copy package descriptors and install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy frontend source code and build production assets
COPY . .
RUN npm run build

# Nginx production stage
FROM nginx:alpine as production

# Copy built production assets to Nginx html directory
COPY --from=build /app/dist /usr/share/nginx/html

# Expose HTTP port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
