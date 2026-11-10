# Etapa 1: compila Angular.
FROM node:22-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx ng build

# Etapa 2: nginx sirve el frontend y reenvía /api y /admin al backend.
FROM nginx:1.27-alpine
COPY deploy/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY deploy/nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY deploy/nginx/proxy-params.conf /etc/nginx/snippets/proxy-params.conf
COPY --from=build /src/dist/frontend/browser /usr/share/nginx/html
EXPOSE 80
