# -----------------------------------------------------------------------
# One-time infrastructure bootstrap:
#   terraform init && terraform apply
# creates the local kind cluster, installs ArgoCD into it, and registers
# the TaskFlow Application so ArgoCD starts watching your GitHub repo.
# Day-to-day deployments never touch Terraform again — they flow through
# git commits (CI builds images, ArgoCD syncs manifests).
# -----------------------------------------------------------------------

resource "kind_cluster" "this" {
  name           = var.cluster_name
  wait_for_ready = true

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    node {
      role = "control-plane"

      # Expose the frontend Service (NodePort 30080) on localhost.
      extra_port_mappings {
        container_port = 30080
        host_port      = var.app_host_port
      }
    }

    node {
      role = "worker"
    }
  }
}

provider "helm" {
  kubernetes {
    host                   = kind_cluster.this.endpoint
    cluster_ca_certificate = kind_cluster.this.cluster_ca_certificate
    client_certificate     = kind_cluster.this.client_certificate
    client_key             = kind_cluster.this.client_key
  }
}

provider "kubectl" {
  host                   = kind_cluster.this.endpoint
  cluster_ca_certificate = kind_cluster.this.cluster_ca_certificate
  client_certificate     = kind_cluster.this.client_certificate
  client_key             = kind_cluster.this.client_key
  load_config_file       = false
}
