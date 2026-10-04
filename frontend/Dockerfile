# InternPilot AI frontend image (design.md §18). Build context: ./frontend
# Stage 1 builds the Vite SPA; stage 2 serves dist/ from an unprivileged nginx (non-root, :8080).

FROM node:22.23.3-alpine AS build
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node package.json package-lock.json .npmrc ./
RUN npm ci --no-audit --no-fund
COPY --chown=node:node . .
# Public API base URL baked into the bundle at build time (Vite inlines VITE_* vars).
# It is visible to every browser, so it must never hold a secret (security.md).
ARG VITE_API_BASE_URL=http://localhost:8000/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27.5-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
# The base image already runs as the unprivileged `nginx` user (uid 101); kept explicit.
USER 101
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["wget", "-q", "--spider", "http://127.0.0.1:8080/"]
