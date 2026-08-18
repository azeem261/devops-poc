resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argocd_chart_version
  namespace        = "argocd"
  create_namespace = true

  # Keep resource usage modest on a laptop cluster.
  values = [yamlencode({
    dex = { enabled = false }
    notifications = { enabled = false }
  })]

  depends_on = [kind_cluster.this]
}

# The ArgoCD "Application" — this is the GitOps contract:
# "keep <namespace taskflow> in sync with <gitops_path> of <gitops_repo_url>".
resource "kubectl_manifest" "taskflow_app" {
  yaml_body = yamlencode({
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata = {
      name      = "taskflow"
      namespace = "argocd"
    }
    spec = {
      project = "default"
      source = {
        repoURL        = var.gitops_repo_url
        targetRevision = var.gitops_revision
        path           = var.gitops_path
      }
      destination = {
        server    = "https://kubernetes.default.svc"
        namespace = "taskflow"
      }
      syncPolicy = {
        automated = {
          prune    = true # delete cluster resources removed from git
          selfHeal = true # revert manual kubectl edits back to git state
        }
        syncOptions = ["CreateNamespace=true"]
      }
    }
  })

  depends_on = [helm_release.argocd]
}
