variable "kubeconfig_path" {
  description = "Path to the kubeconfig file used to reach the target cluster."
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "kubeconfig context to use — \"minikube\" for the local target this phase is built against."
  type        = string
  default     = "minikube"
}

variable "namespace" {
  description = "Namespace the app tier is deployed into. Must already exist — created by `kubectl apply -k k8s/base` (see k8s/base/namespace.yaml), which also owns the `backend-config`/`backend-secrets` ConfigMap/Secret this module reads via envFrom-equivalent env_from blocks. This module intentionally does not create the namespace, Postgres/Redis, or those Config/Secret objects itself — see infra/terraform's own note in DEPLOYMENT.md for why its scope stops at the app tier."
  type        = string
  default     = "traderbot"
}

variable "name_prefix" {
  description = "Prefix for every object this module creates. Defaults to \"tf-\" so a `terraform apply` can run alongside the Kustomize-applied backend/frontend Deployments without colliding — useful for comparing the two apply paths side by side rather than picking one and deleting the other."
  type        = string
  default     = "tf-"
}

variable "backend_image" {
  description = "Backend image reference — \"traderbot-backend:local\" matches what `make minikube-load` loads; swap for a registry-qualified tag once this targets a real cluster (see k8s/overlays/production for the equivalent Kustomize pattern)."
  type        = string
  default     = "traderbot-backend:local"
}

variable "frontend_image" {
  type    = string
  default = "traderbot-frontend:local"
}

variable "backend_replicas" {
  description = "Kept at 1 by default for the same reason as k8s/base/backend-deployment.yaml: the backend runs the market-data/strategy engines as in-process singletons, so more than one replica today means duplicate background work, not more capacity."
  type        = number
  default     = 1
}

variable "frontend_replicas" {
  type    = number
  default = 1
}
