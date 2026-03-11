# NimbusFlow Customer Success FTE — Deployment Guide

**Version:** 2.0.0
**Image:** `nimbusflow/customer-success-fte:latest`
**Namespace:** `customer-success-fte`
**Estimated deployment time:** 20–30 minutes (first time), < 5 minutes (rolling update)

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Infrastructure Setup](#2-infrastructure-setup-first-time-only)
3. [Build and Push Image](#3-build-and-push-image)
4. [Fill Secrets](#4-fill-secrets)
5. [Apply Kubernetes Manifests](#5-apply-kubernetes-manifests)
6. [Verify Deployment](#6-verify-deployment)
7. [Local Development with Docker Compose](#7-local-development-with-docker-compose)
8. [Rolling Update Procedure](#8-rolling-update-procedure)
9. [Rollback Procedure](#9-rollback-procedure)
10. [Teardown](#10-teardown)

---

## 1. Prerequisites

### Required tools

| Tool | Minimum version | Install |
|------|----------------|---------|
| `kubectl` | 1.28+ | https://kubernetes.io/docs/tasks/tools/ |
| `docker` | 24+ | https://docs.docker.com/engine/install/ |
| `helm` | 3.14+ | https://helm.sh/docs/intro/install/ |
| `psql` | 14+ | `apt install postgresql-client` / Homebrew |

### Verify tools are ready

```bash
kubectl version --client
docker version
helm version
psql --version
```

### Cluster access

```bash
# Verify you are connected to the correct cluster:
kubectl cluster-info
kubectl config current-context

# Must have cluster-admin or the following roles:
#   - create/get/list Namespaces
#   - create/get/list/update Deployments, Services, Ingresses
#   - create/get/list Secrets, ConfigMaps
#   - create/get/list HorizontalPodAutoscalers
#   - create/get/list monitoring.coreos.com CRDs (ServiceMonitor, PrometheusRule)
```

### Required environment variables (set these before running commands below)

```bash
export REGISTRY="docker.io/nimbusflow"          # Your Docker registry
export IMAGE_TAG="2.0.0"                         # Version tag to deploy
export DOMAIN="api.nimbusflow.io"                # Your API domain
export DATABASE_URL="postgresql://fte_user:PASSWORD@HOST:5432/fte_db"
export KAFKA_BOOTSTRAP="kafka.customer-success-fte.svc.cluster.local:9092"
```

---

## 2. Infrastructure Setup (first-time only)

These steps install cluster-level dependencies. Skip if already installed.

### 2a. Nginx Ingress Controller

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml

# Wait until the controller pod is Running:
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

# Verify:
kubectl get svc -n ingress-nginx
# Should show an EXTERNAL-IP on the LoadBalancer service
```

### 2b. cert-manager (TLS via Let's Encrypt)

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# Wait for cert-manager pods:
kubectl wait --namespace cert-manager \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/instance=cert-manager \
  --timeout=120s

# Create the ClusterIssuer for Let's Encrypt production:
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ops@nimbusflow.io          # ← Update with your email
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
EOF

# Verify issuer is Ready:
kubectl get clusterissuer letsencrypt-prod
# STATUS column should show: True
```

### 2c. Kafka (using Confluent Helm chart)

```bash
helm repo add confluentinc https://packages.confluent.io/helm
helm repo update

helm install kafka confluentinc/confluent-for-kubernetes \
  --namespace customer-success-fte \
  --create-namespace \
  --set kafka.replicas=3 \
  --set zookeeper.replicas=1

# Wait for Kafka to be ready:
kubectl wait --namespace customer-success-fte \
  --for=condition=ready pod \
  --selector=app=kafka \
  --timeout=300s

# Create required topics:
kubectl exec -it kafka-0 -n customer-success-fte -- \
  kafka-topics --bootstrap-server localhost:9092 --create \
    --topic nimbusflow.messages.email \
    --topic nimbusflow.messages.whatsapp \
    --topic nimbusflow.messages.web_form \
    --partitions 6 \
    --replication-factor 1

kubectl exec -it kafka-0 -n customer-success-fte -- \
  kafka-topics --bootstrap-server localhost:9092 --create \
    --topic nimbusflow.responses.email \
    --topic nimbusflow.responses.whatsapp \
    --topic nimbusflow.responses.web_form \
    --topic nimbusflow.messages.dlq \
    --partitions 3 \
    --replication-factor 1

# Verify:
kubectl exec -it kafka-0 -n customer-success-fte -- \
  kafka-topics --bootstrap-server localhost:9092 --list
```

### 2d. PostgreSQL with pgvector

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm install postgres bitnami/postgresql \
  --namespace customer-success-fte \
  --set auth.database=fte_db \
  --set auth.username=fte_user \
  --set auth.password=CHANGE_THIS_PASSWORD \
  --set primary.persistence.size=20Gi \
  --set image.tag=16

# Wait:
kubectl wait --namespace customer-success-fte \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=postgresql \
  --timeout=120s

# Apply schema:
kubectl exec -it postgres-postgresql-0 -n customer-success-fte -- \
  psql -U fte_user -d fte_db < production/database/schema.sql

# Seed knowledge base (optional but recommended):
kubectl run seed --image=nimbusflow/customer-success-fte:latest \
  --restart=Never \
  --namespace customer-success-fte \
  --env="POSTGRES_HOST=postgres-postgresql.customer-success-fte.svc.cluster.local" \
  --env="POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD" \
  -- python production/database/seed_knowledge_base.py

kubectl wait --for=condition=complete job/seed -n customer-success-fte --timeout=120s
kubectl delete pod seed -n customer-success-fte
```

### 2e. kube-prometheus-stack (monitoring)

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install kube-prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.ruleSelectorNilUsesHelmValues=false \
  --set grafana.adminPassword=admin123   # ← Change this

# Wait:
kubectl wait --namespace monitoring \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=prometheus \
  --timeout=300s

echo "Grafana available at: kubectl port-forward svc/kube-prometheus-grafana -n monitoring 3000:80"
```

### 2f. metrics-server (required for HPA)

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Verify:
kubectl top nodes   # Should show CPU/memory after ~60s
```

---

## 3. Build and Push Image

```bash
# Build multi-stage production image (from repo root):
docker build \
  --target production \
  --tag $REGISTRY/customer-success-fte:$IMAGE_TAG \
  --tag $REGISTRY/customer-success-fte:latest \
  .

# Verify image:
docker run --rm $REGISTRY/customer-success-fte:$IMAGE_TAG \
  python -c "from production.api.main import app; print('Import OK')"

# Push to registry:
docker push $REGISTRY/customer-success-fte:$IMAGE_TAG
docker push $REGISTRY/customer-success-fte:latest
```

---

## 4. Fill Secrets

**Never commit real secret values to git.** Fill these before applying.

### 4a. Encode and apply API secrets

```bash
# Helper: encode a value
b64() { echo -n "$1" | base64; }

# Edit secrets.yaml with real values:
POSTGRES_PW=$(b64 "your-postgres-password")
GEMINI_KEY=$(b64 "AIza...")
OPENAI_KEY=$(b64 "sk-...")
TWILIO_SID=$(b64 "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
TWILIO_TOKEN=$(b64 "your-twilio-auth-token")

# Apply using kubectl create (avoids storing values in files):
kubectl create secret generic fte-secrets \
  --namespace customer-success-fte \
  --from-literal=POSTGRES_PASSWORD="your-postgres-password" \
  --from-literal=GEMINI_API_KEY="AIza..." \
  --from-literal=OPENAI_API_KEY="sk-..." \
  --from-literal=TWILIO_ACCOUNT_SID="ACxxxxxxxx" \
  --from-literal=TWILIO_AUTH_TOKEN="your-twilio-auth-token" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 4b. Gmail OAuth2 credentials

```bash
# Download gmail_credentials.json from Google Cloud Console:
# APIs & Services → Credentials → OAuth 2.0 Client ID → Download JSON
# Rename to gmail_credentials.json

# Generate gmail_token.json by running OAuth2 flow once locally:
python -c "
from google_auth_oauthlib.flow import InstalledAppFlow
flow = InstalledAppFlow.from_client_secrets_file(
    'gmail_credentials.json',
    ['https://www.googleapis.com/auth/gmail.modify']
)
creds = flow.run_local_server(port=0)
import json
with open('gmail_token.json', 'w') as f:
    f.write(creds.to_json())
print('Token saved to gmail_token.json')
"

# Create the Kubernetes secret from the files:
kubectl create secret generic fte-gmail-secrets \
  --namespace customer-success-fte \
  --from-file=gmail_credentials.json=./gmail_credentials.json \
  --from-file=gmail_token.json=./gmail_token.json \
  --dry-run=client -o yaml | kubectl apply -f -

# Verify:
kubectl get secret fte-gmail-secrets -n customer-success-fte
```

### 4c. Update domain in ingress.yaml

```bash
# Replace placeholder domain with your actual domain:
sed -i "s/api.nimbusflow.io/$DOMAIN/g" production/k8s/ingress.yaml
sed -i "s/support.nimbusflow.io/support.$DOMAIN/g" production/k8s/ingress.yaml

# Verify:
grep "host:" production/k8s/ingress.yaml
```

### 4d. Update GCP project in configmap.yaml

```bash
# Update Pub/Sub config:
kubectl patch configmap fte-config \
  -n customer-success-fte \
  --patch '{"data":{"PUBSUB_PROJECT_ID":"your-gcp-project-id","PUBSUB_TOPIC_NAME":"nimbusflow-gmail-push"}}'
```

---

## 5. Apply Kubernetes Manifests

Apply in dependency order. Each step is idempotent — safe to re-run.

```bash
# Step 1: Namespace (must exist before everything else)
kubectl apply -f production/k8s/namespace.yaml
kubectl get namespace customer-success-fte   # Should show Active

# Step 2: ConfigMap (env vars read by pods at startup)
kubectl apply -f production/k8s/configmap.yaml
kubectl get configmap fte-config -n customer-success-fte   # Should exist

# Step 3: Secrets (must exist before deployments reference them)
# Note: If you used `kubectl create secret` in step 4, secrets already exist.
# Only apply if you edited secrets.yaml with base64 values:
kubectl apply -f production/k8s/secrets.yaml
kubectl get secret fte-secrets fte-gmail-secrets -n customer-success-fte

# Step 4: Service (needs to exist before Ingress references it)
kubectl apply -f production/k8s/service.yaml
kubectl get service fte-api -n customer-success-fte

# Step 5: Deployments
kubectl apply -f production/k8s/deployment-api.yaml
kubectl apply -f production/k8s/deployment-worker.yaml

# Step 6: Ingress (after service exists)
kubectl apply -f production/k8s/ingress.yaml

# Step 7: HPAs (after deployments exist)
kubectl apply -f production/k8s/hpa.yaml

# Step 8: Monitoring (after kube-prometheus-stack is installed)
kubectl apply -f production/k8s/monitoring.yaml

# --- Or apply everything at once (after secrets are filled) ---
kubectl apply -f production/k8s/
```

---

## 6. Verify Deployment

Run these checks in order. All must pass before the system is production-ready.

### 6a. Pod status

```bash
# All pods should be Running (API×3, Worker×3):
kubectl get pods -n customer-success-fte -w

# Expected output:
# NAME                          READY   STATUS    RESTARTS   AGE
# fte-api-xxxx-xxxxx            1/1     Running   0          2m
# fte-api-xxxx-xxxxx            1/1     Running   0          2m
# fte-api-xxxx-xxxxx            1/1     Running   0          2m
# fte-worker-xxxx-xxxxx         1/1     Running   0          2m
# fte-worker-xxxx-xxxxx         1/1     Running   0          2m
# fte-worker-xxxx-xxxxx         1/1     Running   0          2m

# If pods are not Running, check events:
kubectl describe pod -l app=fte-api -n customer-success-fte | tail -20
kubectl describe pod -l app=fte-worker -n customer-success-fte | tail -20
```

### 6b. API health checks

```bash
# Port-forward to test locally (or use your Ingress domain):
kubectl port-forward svc/fte-api -n customer-success-fte 8000:80 &

# Liveness:
curl -s http://localhost:8000/health | jq .
# Expected: {"status":"ok","version":"2.0.0","channels":{"email":"...","whatsapp":"...","web_form":"ready"}}

# Readiness (DB + Kafka):
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ready
# Expected: 200

# Metrics endpoint (for Prometheus):
curl -s http://localhost:8000/metrics | head -20
# Expected: Prometheus text format starting with "# HELP ..."

kill %1   # Stop port-forward
```

### 6c. Check logs for errors

```bash
# API pods — look for ERROR lines after startup:
kubectl logs -l app=fte-api -n customer-success-fte --tail=50 | grep -E "ERROR|WARN|Exception"

# Worker pods:
kubectl logs -l app=fte-worker -n customer-success-fte --tail=50 | grep -E "ERROR|WARN|Exception"

# Expected clean startup log (API):
# INFO  Starting NimbusFlow Customer Success FTE API
# INFO  Kafka producer ready, bootstrap=kafka.customer-success-fte.svc.cluster.local:9092
# INFO  Application startup complete.
```

### 6d. HPA status

```bash
kubectl get hpa -n customer-success-fte
# Expected:
# NAME            REFERENCE              TARGETS   MINPODS   MAXPODS   REPLICAS
# fte-api-hpa     Deployment/fte-api     12%/70%   3         20        3
# fte-worker-hpa  Deployment/fte-worker  8%/70%    3         30        3
#
# If TARGETS shows <unknown>/70%, metrics-server may not be installed or pods
# don't have resource requests set.
```

### 6e. TLS certificate

```bash
# Check cert-manager issued the certificate:
kubectl get certificate -n customer-success-fte
# Expected: READY=True

# If READY=False, check the challenge:
kubectl describe certificaterequest -n customer-success-fte
kubectl describe order -n customer-success-fte

# Test HTTPS (replace with your domain):
curl -sv https://$DOMAIN/health 2>&1 | grep "SSL connection\|HTTP/"
```

### 6f. End-to-end smoke test

```bash
# Submit a web form (replace URL with your domain):
curl -s -X POST https://$DOMAIN/support/submit \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "subject": "Deployment smoke test",
    "category": "general",
    "message": "This is an automated smoke test from the deployment guide."
  }' | jq .

# Expected:
# {
#   "ticket_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
#   "message": "Thank you for contacting us!...",
#   "estimated_response_time": "Usually within 5 minutes"
# }
```

### 6g. Monitoring verification

```bash
# Check ServiceMonitor is picked up:
kubectl get servicemonitor -n customer-success-fte
# Expected: fte-api

# Check PrometheusRule is loaded:
kubectl get prometheusrule -n customer-success-fte
# Expected: fte-alerts

# Verify Prometheus is scraping:
kubectl port-forward svc/kube-prometheus-kube-prome-prometheus -n monitoring 9090:9090 &
open http://localhost:9090/targets
# Look for customer-success-fte targets — should show State=UP
kill %1
```

---

## 7. Local Development with Docker Compose

For development and testing without a Kubernetes cluster:

```bash
# Copy example env:
cp .env.example .env

# Fill .env with your real API keys:
#   GEMINI_API_KEY=AIza...
#   OPENAI_API_KEY=sk-...
#   TWILIO_ACCOUNT_SID=ACxxx
#   TWILIO_AUTH_TOKEN=xxx

# Create secrets directory for Gmail files:
mkdir -p secrets
cp gmail_credentials.json secrets/
cp gmail_token.json secrets/

# Start all services:
docker-compose up -d

# Follow logs:
docker-compose logs -f api worker

# Run tests against local stack:
pytest production/tests/ -v --timeout=30

# Check health:
curl http://localhost:8000/health

# Kafka UI: http://localhost:8080

# Stop:
docker-compose down
```

---

## 8. Rolling Update Procedure

Zero-downtime deployment using the rolling update strategy already configured
in `deployment-api.yaml` (`maxSurge=1, maxUnavailable=0`).

```bash
# Step 1: Build and push new image
export NEW_TAG="2.0.1"

docker build --target production \
  -t $REGISTRY/customer-success-fte:$NEW_TAG \
  -t $REGISTRY/customer-success-fte:latest \
  .

docker push $REGISTRY/customer-success-fte:$NEW_TAG
docker push $REGISTRY/customer-success-fte:latest

# Step 2: Update the image tag in both deployments
kubectl set image deployment/fte-api \
  api=$REGISTRY/customer-success-fte:$NEW_TAG \
  -n customer-success-fte

kubectl set image deployment/fte-worker \
  worker=$REGISTRY/customer-success-fte:$NEW_TAG \
  -n customer-success-fte

# Step 3: Monitor rollout progress
kubectl rollout status deployment/fte-api -n customer-success-fte
kubectl rollout status deployment/fte-worker -n customer-success-fte
# Expected: "successfully rolled out"

# Step 4: Verify new pods are healthy
kubectl get pods -n customer-success-fte
curl https://$DOMAIN/health

# Step 5: Annotate the deployment for audit trail
kubectl annotate deployment/fte-api kubernetes.io/change-cause="Deploy v$NEW_TAG" \
  -n customer-success-fte
kubectl annotate deployment/fte-worker kubernetes.io/change-cause="Deploy v$NEW_TAG" \
  -n customer-success-fte
```

### Update ConfigMap without pod restart

```bash
# Edit configmap live:
kubectl edit configmap fte-config -n customer-success-fte

# Trigger rolling restart to pick up new values:
kubectl rollout restart deployment/fte-api -n customer-success-fte
kubectl rollout restart deployment/fte-worker -n customer-success-fte
```

### Update a single Secret value

```bash
# Example: rotate Gemini API key
kubectl patch secret fte-secrets -n customer-success-fte \
  -p "{\"data\":{\"GEMINI_API_KEY\":\"$(echo -n 'new-key-value' | base64)\"}}"

# Restart pods to pick up new secret:
kubectl rollout restart deployment/fte-api -n customer-success-fte
kubectl rollout restart deployment/fte-worker -n customer-success-fte
```

---

## 9. Rollback Procedure

### Immediate rollback (previous image)

```bash
# Check rollout history:
kubectl rollout history deployment/fte-api -n customer-success-fte
kubectl rollout history deployment/fte-worker -n customer-success-fte

# Roll back to previous version:
kubectl rollout undo deployment/fte-api -n customer-success-fte
kubectl rollout undo deployment/fte-worker -n customer-success-fte

# Monitor rollback:
kubectl rollout status deployment/fte-api -n customer-success-fte

# Verify:
curl https://$DOMAIN/health
```

### Rollback to a specific revision

```bash
# List all revisions with change-cause annotations:
kubectl rollout history deployment/fte-api -n customer-success-fte

# Roll back to revision 3:
kubectl rollout undo deployment/fte-api \
  --to-revision=3 \
  -n customer-success-fte

kubectl rollout undo deployment/fte-worker \
  --to-revision=3 \
  -n customer-success-fte
```

### Rollback a ConfigMap change

```bash
# If you know the old value, patch it back:
kubectl patch configmap fte-config -n customer-success-fte \
  --patch '{"data":{"GEMINI_MODEL":"gemini-2.0-flash"}}'

kubectl rollout restart deployment/fte-api -n customer-success-fte
kubectl rollout restart deployment/fte-worker -n customer-success-fte
```

---

## 10. Teardown

```bash
# Remove only the FTE application (keeps infrastructure):
kubectl delete -f production/k8s/
kubectl delete namespace customer-success-fte

# Remove infrastructure (destructive — deletes all data):
helm uninstall postgres -n customer-success-fte
helm uninstall kafka -n customer-success-fte
helm uninstall kube-prometheus -n monitoring

# Remove cert-manager and ingress (shared cluster resources):
kubectl delete -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
kubectl delete -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
```

---

## Quick Reference: Useful Commands

```bash
# Show all FTE resources:
kubectl get all -n customer-success-fte

# Stream all pod logs simultaneously:
kubectl logs -l app.kubernetes.io/name=customer-success-fte \
  -n customer-success-fte -f --prefix=true

# Force restart all pods (e.g., after secret rotation):
kubectl rollout restart deployment/fte-api deployment/fte-worker \
  -n customer-success-fte

# Check resource consumption:
kubectl top pods -n customer-success-fte

# Open exec shell in API pod:
kubectl exec -it deploy/fte-api -n customer-success-fte -- /bin/bash

# Open psql via running pod:
kubectl exec -it deploy/fte-api -n customer-success-fte -- \
  python -c "
import asyncio, asyncpg, os
async def q():
    conn = await asyncpg.connect(
        host=os.getenv('POSTGRES_HOST'), user='fte_user',
        password=os.getenv('POSTGRES_PASSWORD'), database='fte_db'
    )
    rows = await conn.fetch('SELECT COUNT(*) FROM messages')
    print(rows)
asyncio.run(q())
"

# Port-forward Grafana dashboard:
kubectl port-forward svc/kube-prometheus-grafana -n monitoring 3000:80
# Then open http://localhost:3000  (admin / admin123)
```
