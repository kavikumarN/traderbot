.PHONY: build minikube-start minikube-load k8s-secrets k8s-apply k8s-delete \
        k8s-monitoring k8s-monitoring-delete tf-init tf-plan tf-apply tf-destroy \
        port-forward-frontend port-forward-grafana port-forward-prometheus \
        compose-prod-up compose-prod-down compose-monitoring-up

GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
NAMESPACE := traderbot

# --- Images -----------------------------------------------------------------

build: ## Build both images locally, tagged :local
	docker build -t traderbot-backend:local --build-arg GIT_SHA=$(GIT_SHA) ./backend
	docker build -t traderbot-frontend:local --build-arg GIT_SHA=$(GIT_SHA) ./frontend

# --- Minikube -----------------------------------------------------------------

minikube-start: ## Start Minikube with enough headroom for the whole stack + monitoring, and the addons the manifests assume
	minikube start --cpus=4 --memory=6000mb --driver=docker
	minikube addons enable ingress
	minikube addons enable metrics-server

minikube-load: build ## Build then load both images into Minikube's own image cache (no registry needed)
	minikube image load traderbot-backend:local
	minikube image load traderbot-frontend:local

# --- Kubernetes (kubectl / Kustomize) ------------------------------------------

k8s-secrets: ## Create/update the backend-secrets Secret — JWT/Binance values from backend/.env, DB/Redis URLs pinned to the in-cluster Service hostnames (backend/.env's own DATABASE_URL/REDIS_URL point at localhost, which only makes sense outside the cluster)
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	kubectl create secret generic backend-secrets -n $(NAMESPACE) \
		--from-literal=JWT_SECRET_KEY=$$(grep '^JWT_SECRET_KEY=' backend/.env | cut -d= -f2-) \
		--from-literal=BINANCE_API_KEY=$$(grep '^BINANCE_API_KEY=' backend/.env | cut -d= -f2-) \
		--from-literal=BINANCE_API_SECRET=$$(grep '^BINANCE_API_SECRET=' backend/.env | cut -d= -f2-) \
		--from-literal=DATABASE_URL=postgresql+asyncpg://traderbot:traderbot@postgres:5432/traderbot \
		--from-literal=REDIS_URL=redis://redis:6379/0 \
		--from-literal=POSTGRES_PASSWORD=traderbot \
		--dry-run=client -o yaml | kubectl apply -f -

k8s-apply: ## Apply the app (namespace/configmap/postgres/redis/backend/frontend/ingress/hpa) — run k8s-secrets first
	kubectl apply -k k8s/overlays/local

k8s-delete: ## Tear down everything k8s-apply created
	kubectl delete -k k8s/overlays/local

k8s-monitoring: ## Apply the optional Prometheus/Grafana/Loki/Promtail stack
	kubectl apply -k k8s/monitoring

k8s-monitoring-delete:
	kubectl delete -k k8s/monitoring

# --- Terraform (app-tier only — see infra/terraform/main.tf) ------------------

tf-init:
	terraform -chdir=infra/terraform init

tf-plan:
	terraform -chdir=infra/terraform plan

tf-apply:
	terraform -chdir=infra/terraform apply

tf-destroy:
	terraform -chdir=infra/terraform destroy

# --- Local access ---------------------------------------------------------------

port-forward-frontend: ## http://localhost:8080 — same origin the frontend was built with VITE_API_BASE_URL pointing at (adjust if you rebuilt with traderbot.local instead)
	kubectl port-forward -n $(NAMESPACE) svc/frontend 8080:80

port-forward-grafana: ## http://localhost:3000 (admin/admin — see k8s/monitoring/grafana-deployment.yaml)
	kubectl port-forward -n monitoring svc/grafana 3000:3000

port-forward-prometheus: ## http://localhost:9090
	kubectl port-forward -n monitoring svc/prometheus 9090:9090

# --- Docker Compose (non-Kubernetes path) --------------------------------------

compose-prod-up:
	docker compose -f docker-compose.prod.yml up --build -d

compose-prod-down:
	docker compose -f docker-compose.prod.yml down

compose-monitoring-up: ## Layer the monitoring stack onto the dev compose file
	docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
