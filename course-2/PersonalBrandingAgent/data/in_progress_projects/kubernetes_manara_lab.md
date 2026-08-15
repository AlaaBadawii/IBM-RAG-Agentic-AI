# Manara Kubernetes Lab — minikube + nginx deployment (early stage)

## Status
IN PROGRESS (early stage). Source:
`/home/alaabadawii/DevOps/Manara/Kubernetes_lab/`. Part of the Manara DevOps
learning track.

## What this is
Initial Kubernetes practice on a local **minikube** cluster: download the
minikube binary and write a first `Deployment` manifest for nginx.

## Evidence
- `minikube-linux-amd64` — the minikube binary (downloaded).
- `deployment.yaml` — a Kubernetes `Deployment` (apps/v1) named `hello-nginx`,
  1 replica, selector + template with `app: hello-nginx` labels, container
  `image: nginx`.
- `commands.md`, `notes.md` — both EMPTY (no recorded commands/notes yet).

## Technical observation (honest)
The manifest contains invalid keys: `matchLables:` and `lables:` (misspelled
`labels`). These would be rejected by `kubectl apply`. Together with the empty
notes/commands files, this shows the lab was started but not finished or
validated.

## Tools & concepts
Kubernetes (Deployments, labels/selectors, replicas), minikube, kubectl, nginx
containers.

## Accurate classification
IN PROGRESS / early practice. No evidence of a running cluster, a successful
`kubectl apply`, services/ingress, or any real workload. Do NOT claim
Kubernetes competency beyond "started practicing."

## Lessons supported
- Even a two-file lab surfaces real details (label spelling, correct api
  resource) — a good honest story about the first steps into Kubernetes.

## Provenance
`/home/alaabadawii/DevOps/Manara/Kubernetes_lab/deployment.yaml`
`/home/alaabadawii/DevOps/Manara/Kubernetes_lab/minikube-linux-amd64`
`/home/alaabadawii/DevOps/Manara/Kubernetes_lab/commands.md` (empty)
`/home/alaabadawii/DevOps/Manara/Kubernetes_lab/notes.md` (empty)