output "kubeconfig_hint" {
  value = "kind exports kubeconfig automatically; check with: kubectl config use-context kind-${var.cluster_name}"
}

output "argocd_ui" {
  value = <<-EOT
    ArgoCD UI:
      kubectl -n argocd port-forward svc/argocd-server 8443:443
      open https://localhost:8443  (user: admin)
    Initial password:
      kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
  EOT
}

output "app_url" {
  value = "http://localhost:${var.app_host_port} (once ArgoCD has synced the taskflow app)"
}
