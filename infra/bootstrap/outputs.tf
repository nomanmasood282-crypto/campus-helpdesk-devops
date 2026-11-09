output "argocd_namespace" {
  description = "Namespace containing the Argo CD installation."
  value       = kubernetes_namespace_v1.argocd.metadata[0].name
}

output "argocd_server_port_forward" {
  description = "Command to access the Argo CD UI locally."
  value       = "kubectl --context k3d-helpdesk-devops -n argocd port-forward service/argocd-server 8080:443"
}
