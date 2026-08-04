# Multi-stage build producing a slim Next.js standalone server.
FROM node:26-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# npm ci installs exactly what package-lock.json pins (reproducible) and fails
# if package.json and the lockfile drift out of sync.
RUN npm ci

FROM node:26-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Where this server proxies /api/* to: the compose service name, so no API port
# has to be published. Baked in at build time because Next resolves rewrites
# during `next build` (they land in .next/routes-manifest.json).
ARG API_ORIGIN="http://api:8000"
ENV API_ORIGIN=$API_ORIGIN
# Optional: point the browser bundle at an API on another origin instead, bypassing
# the proxy above. Left empty by default so it calls this server's own /api/*.
ARG NEXT_PUBLIC_API_BASE=""
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
RUN npm run build

FROM node:26-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
# Bind the standalone server to all interfaces. Without this, Next binds to the
# Docker-provided $HOSTNAME (the container id), so the compose healthcheck's
# http://127.0.0.1:3000 is refused and the container is marked unhealthy (#127).
ENV HOSTNAME=0.0.0.0
# Copy the standalone server, owned by the built-in non-root `node` user. The
# server only reads these files and serves on $PORT (no runtime writes), so
# dropping root is safe (defence in depth, #55).
COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
