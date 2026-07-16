# syntax=docker/dockerfile:1

# ---- builder: install deps and produce the static `dist/` bundle ----------
FROM node:20-slim AS builder

WORKDIR /build

# Dependency layer cached separately from source so a source-only change
# doesn't re-run `npm ci` — same reasoning as backend/Dockerfile's builder
# stage.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite bakes VITE_* vars into the bundle at build time (not read at
# container runtime), so this has to be a build-arg, not a runtime env var.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ---- runtime: nginx serving the static bundle + reverse-proxying /api -----
FROM nginx:1.27-alpine AS runtime

ARG GIT_SHA=unknown
LABEL org.opencontainers.image.revision=$GIT_SHA

RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

# The base image's master process starts as root (needed to bind port 80)
# but its worker processes — the ones actually handling requests — already
# drop to the unprivileged `nginx` user via the base `nginx.conf`'s `user`
# directive, which this only overrides at the conf.d/server-block level.

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
