# Stage 1: Build static files
FROM node:20-slim AS builder

WORKDIR /app

COPY app/frontend/package.json app/frontend/package-lock.json* ./
RUN npm install

# API base URL (baked into static bundle at build time)
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

COPY app/frontend/ ./
RUN npx vite build

# Stage 2: Serve with nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# nginx config
RUN echo 'server { \
    listen 5173; \
    server_name _; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 5173

CMD ["nginx", "-g", "daemon off;"]
