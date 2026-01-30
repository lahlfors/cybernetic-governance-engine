variable "project_id" {
  description = "The Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "The Google Cloud Region"
  type        = string
  default     = "us-central1"
}

variable "opa_auth_token" {
  description = "The authentication token for OPA"
  type        = string
  sensitive   = true
}
