# Multi-stage build producing a slim Next.js standalone server.
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# npm ci installs exactly what package-lock.json pins (reproducible) and fails
# if package.json and the lockfile drift out of sync.
RUN npm ci

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Optional: pin the API URL the browser bundle calls. Left empty by default so
# the frontend derives it from the host the page is loaded from (see api-base.ts).
ARG NEXT_PUBLIC_API_BASE=""
ARG NEXT_PUBLIC_API_PORT="8000"
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_PORT=$NEXT_PUBLIC_API_PORT
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
