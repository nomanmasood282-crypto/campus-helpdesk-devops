terraform {
  required_version = ">= 1.6.0"

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.38"
    }
  }
}

provider "kubernetes" {
  config_path    = pathexpand("~/.kube/config")
  config_context = "k3d-helpdesk-devops"
}

provider "helm" {
  kubernetes = {
    config_path    = pathexpand("~/.kube/config")
    config_context = "k3d-helpdesk-devops"
  }
}

resource "kubernetes_namespace_v1" "argocd" {
  metadata {
    name = "argocd"
    labels = {
      "app.kubernetes.io/part-of" = "argocd"
    }
  }
}

resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = "10.16.0"
  namespace  = kubernetes_namespace_v1.argocd.metadata[0].name

  values = [
    yamlencode({
      repoServer = {
        resources = {
          requests = {
            cpu    = "100m"
            memory = "256Mi"
          }
          limits = {
            cpu    = "500m"
            memory = "768Mi"
          }
        }
        livenessProbe = {
          initialDelaySeconds = 30
          timeoutSeconds      = 10
          failureThreshold    = 10
        }
        readinessProbe = {
          initialDelaySeconds = 30
          timeoutSeconds      = 10
          failureThreshold    = 10
        }
      }
    })
  ]

  atomic          = true
  cleanup_on_fail = true
  timeout         = 600
  wait            = true
}
