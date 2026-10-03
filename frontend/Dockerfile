FROM node:22-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
ARG VITE_PUBLIC_REGISTRATION_ENABLED=false
ARG VITE_ENABLE_DEMO_TOOLS=false
ENV VITE_PUBLIC_REGISTRATION_ENABLED=${VITE_PUBLIC_REGISTRATION_ENABLED} \
    VITE_ENABLE_DEMO_TOOLS=${VITE_ENABLE_DEMO_TOOLS}
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
