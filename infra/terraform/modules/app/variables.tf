variable "namespace" {
  type = string
}

variable "name_prefix" {
  type    = string
  default = "tf-"
}

variable "backend_image" {
  type = string
}

variable "frontend_image" {
  type = string
}

variable "backend_replicas" {
  type    = number
  default = 1
}

variable "frontend_replicas" {
  type    = number
  default = 1
}

variable "config_map_name" {
  description = "Name of the existing ConfigMap (created by k8s/base) to source backend env vars from."
  type        = string
  default     = "backend-config"
}

variable "secret_name" {
  description = "Name of the existing Secret (created out-of-band — see k8s/base/secret.example.yaml) to source backend secrets from."
  type        = string
  default     = "backend-secrets"
}
