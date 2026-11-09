# Campus Helpdesk Ticket API

A small FastAPI service for creating and tracking campus support tickets. It is the application component of a local-first DevOps platform using Docker, Kubernetes, Helm, Terraform, GitOps, CI, and monitoring.

## Current milestone

- Create, list, filter, retrieve, and update ticket status.
- SQLite persistence.
- Liveness and readiness endpoints.
- Prometheus request count and duration metrics.
- Automated API tests.
- Non-root Docker image.
- Helm chart with probes, resource requests/limits, and persistent ticket storage.
- GitHub Actions workflow for tests, image scanning, GHCR publishing, and GitOps image updates on pushes to `main`.
- Terraform-managed Argo CD bootstrap and GitOps application definitions for the API and monitoring stack.

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn ticket_api.main:app --app-dir src --reload
```

The API documentation is available at `http://127.0.0.1:8000/docs`. Data is stored in `data/tickets.db`.

Run the tests with:

```powershell
python -m pytest
```

## Build the container

```powershell
docker build -t campus-helpdesk-api:0.1.0 .
docker run --rm -p 8000:8000 campus-helpdesk-api:0.1.0
```

## Helm chart

Validate and render the chart locally:

```powershell
helm lint deploy\helm\helpdesk
helm template helpdesk deploy\helm\helpdesk --namespace helpdesk
```

The chart defaults to one API replica, a local-path persistent volume for SQLite, and HTTP health probes. The optional ServiceMonitor template is disabled by default; the lightweight Prometheus setup scrapes only the API metrics endpoint directly.

## Local Kubernetes cluster

Docker Desktop must be running. The project cluster is independent of other local clusters and does not change the default kubectl context:

```powershell
k3d cluster create helpdesk-devops --servers 1 --agents 0 --servers-memory 3g --kubeconfig-update-default=true --kubeconfig-switch-context=false
kubectl --context k3d-helpdesk-devops get nodes
```

Start and stop this cluster without deleting it:

```powershell
k3d cluster start helpdesk-devops
k3d cluster stop helpdesk-devops
```

## Terraform platform bootstrap

Terraform manages the Argo CD namespace and installation in the dedicated local `helpdesk-devops` cluster. Argo CD will manage application deployments from Git; Terraform and Argo CD are intentionally assigned different resources.

```powershell
terraform -chdir=infra\bootstrap init
terraform -chdir=infra\bootstrap plan
terraform -chdir=infra\bootstrap apply
```

Terraform uses the `k3d-helpdesk-devops` kubeconfig context. The generated local state file is ignored by Git and should remain private.

The Argo CD manifests are configured to use this repository. After pushing it to GitHub, install the root application:

```powershell
kubectl --context k3d-helpdesk-devops apply -f deploy\argocd\root.yaml
```

The root application discovers the API, Prometheus, Grafana, and dashboard applications. Argo CD syncs the API chart from Git, installs Prometheus and Grafana from pinned Helm charts, and provisions the API dashboard. Prometheus scrapes only the helpdesk API; optional Kubernetes exporters and persistent monitoring storage are disabled to keep the local cluster lightweight. A successful push to `main` builds and scans the image, publishes it to GHCR, and commits the new image repository and commit-SHA tag to the Helm values; Argo CD then reconciles that Git change.

Open Grafana locally with port forwarding:

```powershell
kubectl --context k3d-helpdesk-devops -n monitoring port-forward service/grafana 3000:80
```

Visit `http://localhost:3000` and sign in as `admin`. Retrieve the generated password in PowerShell:

```powershell
$encodedPassword = kubectl --context k3d-helpdesk-devops -n monitoring get secret grafana -o jsonpath="{.data.admin-password}"
[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($encodedPassword))
```

## CI and image publishing

GitHub Actions runs tests on pull requests and pushes to `main`, then builds and scans the image. A push to `main` publishes a commit-SHA-tagged image to GHCR using the workflow's automatically provided `GITHUB_TOKEN`; no separate registry credential is required. Publishing happens only after the image scan passes. Make the GHCR package public in GitHub package settings so the local cluster can pull it without storing a registry credential. No cloud account is used or needed.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/tickets` | Create a ticket |
| `GET` | `/tickets` | List tickets; optionally filter with `?status=open` |
| `GET` | `/tickets/{ticket_id}` | Retrieve a ticket |
| `PATCH` | `/tickets/{ticket_id}` | Update its status |
| `GET` | `/health/live` | Check that the API process is running |
| `GET` | `/health/ready` | Check that the database is reachable |
| `GET` | `/metrics` | Expose Prometheus metrics |

Valid ticket statuses are `open`, `in_progress`, and `resolved`.
