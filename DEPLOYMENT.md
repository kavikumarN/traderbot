# Deployment Guide

Three ways to run this stack beyond `docker-compose.yml`'s local dev setup, from simplest to most complete:

1. **[Docker Compose (prod-like)](#1-docker-compose-prod-like)** — one host, no Kubernetes.
2. **[Kubernetes via Minikube](#2-kubernetes-via-minikube)** — the primary target for this phase, fully local, no cloud account needed.
3. **[Terraform](#3-terraform-app-tier-only)** — an alternative, state-tracked way to apply just the backend/frontend app tier onto the same Minikube cluster.

All three assume you've already got a working local dev setup (`docker-compose.yml`, `backend/.env` copied from `backend/.env.example` and filled in — see [Environment variables](#environment-variables) below for the full list).

---

## 1. Docker Compose (prod-like)

```bash
docker compose -f docker-compose.prod.yml up --build -d
# or: make compose-prod-up
```

Differences from the dev `docker-compose.yml`: no bind-mounted source, no `--reload`, no Postgres port published to the host, backend secrets come from `env_file: backend/.env` instead of being inlined, and there's now a `frontend` service (nginx serving the built SPA + reverse-proxying `/api/` and `/health/` to `backend:8000` — see `frontend/nginx.conf`).

Open **http://localhost:8080**. Tear down with `make compose-prod-down`.

**Monitoring add-on** (optional, works against either compose file):

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
# or: make compose-monitoring-up
```

Grafana at http://localhost:3000 (`admin`/`admin`), Prometheus at http://localhost:9090.

---

## 2. Kubernetes via Minikube

This is the deployment target this phase was actually built and verified against — `minikube`, `kubectl`, and `terraform` are assumed installed locally.

```bash
make minikube-start        # minikube start --cpus=4 --memory=6000mb; enables ingress + metrics-server addons
make minikube-load         # docker build both images, then `minikube image load` them (no registry needed)
make k8s-secrets           # creates the traderbot namespace + backend-secrets Secret from backend/.env
make k8s-apply             # kubectl apply -k k8s/overlays/local
```

Wait for everything to come up:

```bash
kubectl get pods -n traderbot -w
```

Add the Ingress host to `/etc/hosts` (or Windows' `C:\Windows\System32\drivers\etc\hosts`):

```
<minikube ip>  traderbot.local
```

(`minikube ip` prints the address.) Then open **http://traderbot.local**.

> **Frontend image caveat**: `VITE_API_BASE_URL` is baked into the frontend bundle at *build* time (Vite inlines `VITE_*` vars — there's no runtime env for a static SPA without extra tooling this phase doesn't add). `make minikube-load` builds with the Dockerfile's default (`http://localhost:8000`), which won't match `http://traderbot.local`. Rebuild explicitly for the Ingress host before relying on it end-to-end:
> ```bash
> docker build -t traderbot-frontend:local --build-arg VITE_API_BASE_URL=http://traderbot.local ./frontend
> minikube image load traderbot-frontend:local
> kubectl rollout restart deployment/frontend -n traderbot
> ```
> `make port-forward-frontend` (below) sidesteps this entirely for a quick check, since it's already built against `http://localhost:8080`... which also won't match a plain `kubectl port-forward` to port 8080. The cleanest path for local verification: forward to whatever port you built the image against, or just rebuild for `http://localhost:<forwarded-port>` before forwarding.

**Quick access without the Ingress/hosts-file step:**

```bash
make port-forward-frontend   # http://localhost:8080
```

**Monitoring:**

```bash
make k8s-monitoring
make port-forward-grafana     # http://localhost:3000, admin/admin
make port-forward-prometheus  # http://localhost:9090
```

Grafana ships with a "Traderbot Overview" dashboard (request rate, p95 latency, 5xx rate, backend logs) provisioned automatically from `deploy/grafana/provisioning/dashboards/json/traderbot-overview.json` (Compose path) / `k8s/monitoring/config/traderbot-overview.json` (K8s path — a physical copy, see `k8s/monitoring/kustomization.yaml`'s own note on why).

**Tear down:**

```bash
make k8s-monitoring-delete
make k8s-delete
minikube stop   # or `minikube delete` to reclaim disk entirely
```

### Why replicas are capped at 1 for the backend

`app/main.py`'s lifespan starts the market-data engine and strategy engine as **in-process singletons** — one shared WebSocket connection per symbol, one `asyncio.Task` per running strategy, for the process's lifetime. A second backend pod would run a second, fully independent copy of both: duplicate WebSocket streams, duplicate strategy evaluation, duplicate order placement. `k8s/base/backend-deployment.yaml` and its `hpa.yaml` are both capped at 1 replica for this reason — it's a correctness constraint, not a resource-sizing placeholder. Scaling the backend safely needs the background workers split out of the API process first (a separate worker Deployment + leader election, or similar); that's out of scope here. The frontend has no such constraint and scales freely (`k8s/base/frontend-deployment.yaml` defaults to 2 replicas, its HPA to 2–5).

### Production-cluster caveat

`k8s/overlays/production/` is a **placeholder** — swap `REGISTRY_PLACEHOLDER` for a real registry and the Ingress host for a real domain before ever applying it; it isn't wired to any actual cloud infrastructure. If/when this moves to a real managed Kubernetes cluster (EKS/GKE/AKS), one thing won't carry over as-is: `k8s/base/postgres-statefulset.yaml` uses `timescale/timescaledb`, and managed Postgres services (RDS, Cloud SQL) generally don't ship the TimescaleDB extension — that would need either Timescale Cloud or a self-managed instance, not a drop-in swap of the StatefulSet's image for a managed one.

---

## 3. Terraform (app tier only)

`infra/terraform/` uses the `hashicorp/kubernetes` provider against your local `minikube` kubeconfig context — no cloud credentials, no state backend beyond local `terraform.tfstate` (gitignored). It **only** manages the backend/frontend Deployments/Services — Postgres, Redis, the namespace, and the ConfigMap/Secret it reads are all owned by Kustomize (`k8s/base`), applied first. It's an alternative way to apply *that one part*, not a replacement for the rest.

Every object it creates is prefixed `tf-` by default (`var.name_prefix`) specifically so it can run **alongside** the Kustomize-applied `backend`/`frontend` without colliding — useful for comparing the two apply paths, not something you'd run permanently side by side in a real environment.

```bash
make k8s-secrets   # backend-secrets must already exist (see above)
make k8s-apply     # namespace/configmap/postgres/redis must already exist too
make tf-init
make tf-plan
make tf-apply
```

Copy `infra/terraform/environments/local.tfvars.example` to `local.tfvars` (gitignored) if you need to override any default — most `minikube start` setups won't.

```bash
make tf-destroy   # tears down only the tf-* objects
```

---

## CI/CD

- **`.github/workflows/ci.yml`** — on every push/PR: backend (`ruff check`, `pytest` — every test runs against in-memory fakes, no service containers needed) and frontend (`oxlint`, `tsc -b`, `vite build`) as two independent jobs.
- **`.github/workflows/cd.yml`** — on push to `main` or a `v*` tag: builds and pushes both images to GHCR (`ghcr.io/<org>/<repo>-backend`, `-frontend`), tagged `latest` + short SHA, using the built-in `GITHUB_TOKEN` (no extra secret to configure). **Does not deploy anywhere** — a GitHub-hosted runner can't reach a local Minikube cluster; getting a pushed image running is the manual `make minikube-load`/`make k8s-apply` (or `k8s/overlays/production` once that's pointed at a real cluster) flow above.

---

## Secrets management

| Environment | Mechanism |
|---|---|
| Local dev | `backend/.env` (gitignored), read directly by `pydantic-settings` |
| Compose-prod | Same `backend/.env`, referenced via `env_file:` in `docker-compose.prod.yml` (never inlined) |
| Kubernetes | A `backend-secrets` Secret, created via `make k8s-secrets` (from `backend/.env`) or manually per `k8s/base/secret.example.yaml`'s header comment. That file is a **template only** — placeholder values, deliberately excluded from `k8s/base/kustomization.yaml`'s `resources:` so `kubectl apply -k` can never apply it by accident. |
| Terraform | Reads the same `backend-secrets` Secret via `env_from { secret_ref { ... } }` (`infra/terraform/modules/app/main.tf`) — doesn't create or duplicate it. |
| CI/CD | `GITHUB_TOKEN` only (built-in, scoped to `packages: write`) — no long-lived credentials stored anywhere. |

None of this is production-grade secret rotation/auditing (that's Vault, External Secrets Operator, SOPS, or a cloud secrets manager, depending on where this ends up) — it's the minimum that keeps real values out of git while staying simple enough to actually run locally.

---

## Environment variables

Every field `backend/app/core/config.py`'s `Settings` class declares (also documented inline in `backend/.env.example`):

| Var | Default | Notes |
|---|---|---|
| `APP_NAME` | `traderbot-backend` | |
| `ENVIRONMENT` | `local` | `local`\|`staging`\|`production`\|`test` |
| `DEBUG` | `false` | |
| `LOG_LEVEL` | `INFO` | `DEBUG`\|`INFO`\|`WARNING`\|`ERROR` |
| `LOG_FORMAT` | `json` | `console` for local dev readability, `json` for anything whose logs get shipped (Promtail/Loki expect this) |
| `API_V1_PREFIX` | `/api/v1` | |
| `CORS_ORIGINS` | `[]` | JSON array or comma-separated string |
| `DATABASE_URL` | *(required)* | `postgresql+asyncpg://...` — secret |
| `DATABASE_POOL_SIZE` | `10` | |
| `DATABASE_MAX_OVERFLOW` | `5` | |
| `DATABASE_ECHO` | `false` | |
| `REDIS_URL` | *(required)* | secret |
| `JWT_SECRET_KEY` | *(required, min 32 chars)* | secret — generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |
| `PASSWORD_MIN_LENGTH` | `10` | |
| `BINANCE_API_KEY` / `BINANCE_API_SECRET` | `None` | secret — optional; public market data needs none, only account/order endpoints (`TRADING_MODE=live`) do |
| `BINANCE_REST_BASE_URL` | `https://api.binance.com` | |
| `BINANCE_WS_BASE_URL` | `wss://stream.binance.com:9443` | |
| `BINANCE_RECV_WINDOW_MS` | `5000` | |
| `BINANCE_REQUEST_WEIGHT_LIMIT` / `_WINDOW_SECONDS` | `6000` / `60.0` | |
| `BINANCE_ORDER_LIMIT` / `_WINDOW_SECONDS` | `100` / `10.0` | |
| `BINANCE_MAX_RETRIES` | `3` | |
| `BINANCE_RETRY_BASE_DELAY_SECONDS` | `0.5` | |
| `MARKET_DATA_SYMBOLS` | `BTCUSDT,ETHUSDT` | set to empty to disable the market-data engine entirely |
| `MARKET_DATA_CANDLE_INTERVALS` | `1m` | |
| `MARKET_DATA_ORDER_BOOK_PERSIST_INTERVAL_SECONDS` | `1.0` | |
| `TRADING_MODE` | `paper` | `paper`\|`live` — defaults safe: a fresh deployment can never place a real order by accident |
| `PAPER_TRADING_STARTING_BALANCE_USDT` | `100000` | |
| `PAPER_TRADING_COMMISSION_RATE` | `0.001` | |

Frontend has exactly one: `VITE_API_BASE_URL` (build-time only — see the Minikube section's caveat above).

---

## Health checks, metrics, logging

- **`GET /health/live`** — always `200`, no dependency checks. Docker `HEALTHCHECK` (`backend/Dockerfile`) and K8s `livenessProbe` (`k8s/base/backend-deployment.yaml`) both use this.
- **`GET /health/ready`** — checks DB + Redis, `200` if both `ok` else `503` with a per-check breakdown. Used as the K8s `readinessProbe`.
- **`GET /metrics`** — Prometheus-format, via `prometheus-fastapi-instrumentator` (wired in `backend/app/main.py`'s `create_app()`). Request count/latency/in-progress by route+method+status, no custom instrumentation needed. Scraped by `deploy/prometheus/prometheus.yml` (Compose) / `k8s/monitoring/prometheus-configmap.yaml` (K8s).
- **Logging**: structured JSON to stdout already (`backend/app/core/logging.py`), with an `X-Request-ID`-correlated `request_id` field on every line (`RequestIdMiddleware`). This phase adds *shipping*: Promtail tails container/pod stdout and pushes to Loki, queryable from Grafana's "Backend Logs" panel or Loki's own datasource directly. No app-side changes were needed for this — it was already emitting the right shape.

---

## Rollback

- **Compose**: `docker compose -f docker-compose.prod.yml down`, then `up` again with the previous image tag (rebuild from a previous git commit, or `docker tag` a previously-pushed GHCR image locally).
- **Kubernetes**: `kubectl rollout undo deployment/backend -n traderbot` (or `frontend`) — standard Deployment rollout history, works as long as you haven't pruned it. For an image built outside the cluster's own history (e.g. reverting further back than `kubectl` remembers), rebuild+reload the old commit's images and re-apply.
- **Terraform**: `terraform apply` with `-var backend_image=...`/`-var frontend_image=...` pointing at a previous tag re-converges the `tf-*` objects to that image.

Database migrations (`alembic upgrade head`, run via the backend Deployment's `initContainer` / Compose's `command:`) are **forward-only** in this setup — there's no automatic downgrade wired into rollback. Reverting a migration means running `alembic downgrade <revision>` manually before rolling the app back, if the schema change isn't backward-compatible with the older code.
