# Kubernetes deployment

A kustomize-based deployment of the full pipeline. No host-specific values live
in these manifests — everything is supplied by you via `kubernetes/.env` and a
TLS secret, so the same manifests run on any cluster.

## What gets deployed

| Resource | Purpose |
|---|---|
| `imap` Deployment + Service | Dovecot mailbox; exposes IMAPS `993` + LMTP `24` via a `LoadBalancer` |
| `mail-processor` Deployment | The fetch → AI-scan → deliver loop |
| `antivirus` Deployment | ClamAV daemon |
| `daily-briefing` Deployment | Scheduled security/health briefing |
| `postal-inspector-config` ConfigMap | Non-secret tunables (`configmap.yaml`) |
| `postal-inspector-secrets` Secret | Generated from `.env` by kustomize |
| `maildir` / `clamav-data` PVCs | Mail storage + virus signatures |

## Prerequisites

- A Kubernetes cluster with a default `StorageClass` (or set one in `pvc.yaml`).
- A `LoadBalancer` provider (cloud LB, or MetalLB on bare metal). No LB? Change
  the imap Service `type` to `NodePort`.
- The three app images built and available to the cluster (next step).

## 1. Build images

```bash
# from the repo root
docker compose build imap mail-processor daily-briefing
```

Make them reachable by the cluster — either push to a registry and set the names
in `kustomization.yaml` (`images:`), or, on a single-node cluster, import them
into the node's container runtime, e.g.:

```bash
docker save postal-inspector-imap:latest | sudo k0s ctr -n k8s.io images import -
# (repeat for mail-processor and daily-briefing)
```

## 2. Configure secrets

```bash
cp kubernetes/.env.example kubernetes/.env   # .env is gitignored
$EDITOR kubernetes/.env                       # API key, mailbox + upstream creds, domain
```

## 3. Provide the IMAPS TLS secret

Either with cert-manager (copy `certificate.example.yaml` → `certificate.yaml`,
set your domain + ClusterIssuer, and add it to `kustomization.yaml` resources),
or manually from your own cert:

```bash
kubectl create namespace postal-inspector
kubectl -n postal-inspector create secret tls imap-tls \
  --cert=fullchain.pem --key=privkey.pem
```

## 4. Deploy

```bash
kubectl apply -k kubernetes/
kubectl -n postal-inspector get pods
```

## Exposing it

The imap Service is a `LoadBalancer`. Point a DNS record at its external IP and
forward TCP `993` to it. To automate DNS/NAT, add the relevant provider
annotations to the Service (e.g. external-dns) — intentionally omitted here so
the base stays portable.
