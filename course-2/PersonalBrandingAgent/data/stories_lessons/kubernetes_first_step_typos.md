# Kubernetes: My First Manifest Had Three Typos

## Type

Learning

## Context

First Kubernetes practice on minikube in `/home/alaabadawii/DevOps/Manara/Kubernetes_lab/`.
Downloaded the minikube binary and wrote a first `Deployment` manifest for nginx.

## Problem

The initial manifest was not valid: it contained misspelled keys (`matchLables:`
and `lables:` instead of `labels`), which `kubectl apply` would reject. The
notes/commands files were also empty — the lab was started but not finished or
validated.

## What I Did

Wrote a first `Deployment` (apps/v1) with selector + template labels for an
nginx container, downloaded minikube, and attempted the first steps of running a
local cluster.

## Decision / Insight

Even two YAML files surface real details: label selectors must match the
template labels exactly, keys must be spelled correctly, and the right API
resource (`apps/v1` Deployment) matters. YAML validity is caught only by
applying — or by careful review.

## Result

No running cluster or applied workload yet. This is early, in-progress practice.
The honest endpoint: I am at the very beginning of Kubernetes, not operating
clusters.

## Engineering Lesson

First attempts have rough edges — and that is normal. The discipline is to
declare what is actually done (in progress / early), not to overstate it. A
misspelled key is exactly what `kubectl apply` — or a careful re-read — catches.

## Why This Matters

Production engineering / DevOps is a stated direction; Kubernetes is on the
learning path (also a future target in the vision). But this story must remain an
honest "I'm starting to learn Kubernetes," not a competency claim.

## Evidence

- `/home/alaabadawii/DevOps/Manara/Kubernetes_lab/deployment.yaml` (invalid keys)
- `/home/alaabadawii/DevOps/Manara/Kubernetes_lab/minikube-linux-amd64`
- `/home/alaabadawii/DevOps/Manara/Kubernetes_lab/commands.md` (empty)
- KB: `in_progress_projects/kubernetes_manara_lab.md`,
  `evidence/devops/devops.md`

## Content Potential

- Honest learning journey post ("my first Kubernetes manifest had typos")
- Contrast: learning vs demonstrated competency in Kubernetes

Story strength:
WEAK

Reason:
Real first-hand event and honest scoping, but it is primarily an early-learning
artifact with no deployed result and little engineering judgment demonstrated so
far. Keep as an honest starting point, not a headline story.