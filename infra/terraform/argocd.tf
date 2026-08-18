resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argocd_chart_version
  namespace        = "argocd"
  create_namespace = true

  # Keep resource usage modest on a laptop cluster.
  values = [yamlencode({
    dex           = { enabled = false }
    notifications = { enabled = false }
  })]

  depends_on = [kind_cluster.this]
}

# The taskflow Application lives in its own tiny local chart
# (charts/argocd-apps) installed AFTER the argocd release: Helm validates
# every object against the cluster API before installing, so an Application
# CR can only be applied once ArgoCD's CRDs already exist in the cluster.
resource "helm_release" "argocd_apps" {
  name      = "argocd-apps"
  chart     = "${path.module}/charts/argocd-apps"
  namespace = "argocd"

  set {
    name  = "repoURL"
    value = var.gitops_repo_url
  }
  set {
    name  = "targetRevision"
    value = var.gitops_revision
  }
  set {
    name  = "path"
    value = var.gitops_path
  }

  depends_on = [helm_release.argocd]
}
