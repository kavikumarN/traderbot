# image_pull_policy = "Never" everywhere below matches k8s/overlays/local's
# Kustomize patch: images are `minikube image load`ed, not pulled from a
# registry, for this phase's local-Minikube target.

resource "kubernetes_deployment_v1" "backend" {
  metadata {
    name      = "${var.name_prefix}backend"
    namespace = var.namespace
    labels    = { app = "${var.name_prefix}backend" }
  }

  spec {
    replicas = var.backend_replicas

    selector {
      match_labels = { app = "${var.name_prefix}backend" }
    }

    template {
      metadata {
        labels = { app = "${var.name_prefix}backend" }
      }

      spec {
        container {
          name              = "backend"
          image             = var.backend_image
          image_pull_policy = "Never"

          port {
            container_port = 8000
          }

          env_from {
            config_map_ref {
              name = var.config_map_name
            }
          }
          env_from {
            secret_ref {
              name = var.secret_name
            }
          }

          liveness_probe {
            http_get {
              path = "/health/live"
              port = 8000
            }
            initial_delay_seconds = 10
            period_seconds        = 15
          }

          readiness_probe {
            http_get {
              path = "/health/ready"
              port = 8000
            }
            initial_delay_seconds = 10
            period_seconds        = 10
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "backend" {
  metadata {
    name      = "${var.name_prefix}backend"
    namespace = var.namespace
  }

  spec {
    selector = { app = "${var.name_prefix}backend" }

    port {
      port        = 8000
      target_port = 8000
    }
  }
}

resource "kubernetes_deployment_v1" "frontend" {
  metadata {
    name      = "${var.name_prefix}frontend"
    namespace = var.namespace
    labels    = { app = "${var.name_prefix}frontend" }
  }

  spec {
    replicas = var.frontend_replicas

    selector {
      match_labels = { app = "${var.name_prefix}frontend" }
    }

    template {
      metadata {
        labels = { app = "${var.name_prefix}frontend" }
      }

      spec {
        container {
          name              = "frontend"
          image             = var.frontend_image
          image_pull_policy = "Never"

          port {
            container_port = 80
          }

          liveness_probe {
            http_get {
              path = "/healthz"
              port = 80
            }
            initial_delay_seconds = 5
            period_seconds        = 15
          }

          readiness_probe {
            http_get {
              path = "/healthz"
              port = 80
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          resources {
            requests = {
              cpu    = "50m"
              memory = "64Mi"
            }
            limits = {
              cpu    = "200m"
              memory = "128Mi"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "frontend" {
  metadata {
    name      = "${var.name_prefix}frontend"
    namespace = var.namespace
  }

  spec {
    selector = { app = "${var.name_prefix}frontend" }

    port {
      port        = 80
      target_port = 80
    }
  }
}
