variable "cluster_name" {
  description = "Name of the local kind cluster."
  type        = string
  default     = "devops-poc"
}

variable "gitops_repo_url" {
  description = "HTTPS URL of the GitHub repo ArgoCD should watch, e.g. https://github.com/<you>/devops-poc.git (must be public, or you'll need to add repo credentials in ArgoCD)."
  type        = string
}

variable "gitops_revision" {
  description = "Branch/tag ArgoCD tracks."
  type        = string
  default     = "main"
}

variable "gitops_path" {
  description = "Path inside the repo that ArgoCD deploys."
  type        = string
  default     = "gitops/overlays/dev"
}

variable "app_host_port" {
  description = "Host port mapped to the frontend NodePort (30080) inside the cluster."
  type        = number
  default     = 8080
}

variable "argocd_chart_version" {
  description = "argo-cd Helm chart version. null = latest available."
  type        = string
  default     = null
}
