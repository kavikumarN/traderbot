# Deliberately scoped to the backend+frontend app tier only — Postgres,
# Redis, the namespace, monitoring, and the ConfigMap/Secret this module
# reads are all owned by Kustomize (k8s/base, k8s/monitoring), not
# duplicated here in HCL. This module demonstrates the IaC-with-state-
# tracking pattern for the one part of the stack most likely to be
# redeployed frequently (application code, not infrastructure), for teams
# who'd rather `terraform apply` than run raw `kubectl`/`kustomize`.

module "app" {
  source = "./modules/app"

  namespace         = var.namespace
  name_prefix       = var.name_prefix
  backend_image     = var.backend_image
  frontend_image    = var.frontend_image
  backend_replicas  = var.backend_replicas
  frontend_replicas = var.frontend_replicas
}
