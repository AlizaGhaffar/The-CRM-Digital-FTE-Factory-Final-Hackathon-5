#!/usr/bin/env bash
# ============================================================
# NimbusFlow Customer Success FTE — Deployment Script
#
# Usage:
#   ./scripts/deploy.sh                    # Full deployment
#   ./scripts/deploy.sh --secrets-only     # Apply secrets only
#   ./scripts/deploy.sh --skip-build       # Deploy without rebuilding image
#   ./scripts/deploy.sh --skip-infra       # Skip infrastructure checks
#   ./scripts/deploy.sh --env staging      # Deploy to staging namespace
#   ./scripts/deploy.sh --tag 2.0.1        # Deploy specific image tag
#   ./scripts/deploy.sh --dry-run          # Validate without applying
#
# Requirements:
#   - kubectl connected to your cluster
#   - docker logged in to registry
#   - .env file with API keys (or export variables directly)
#   - secrets/gmail_credentials.json and secrets/gmail_token.json
# ============================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'  # No Colour

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
step()    { echo -e "\n${BOLD}${BLUE}──── $* ────${NC}"; }
die()     { error "$*"; exit 1; }

# ── Defaults ─────────────────────────────────────────────────────────────────
NAMESPACE="customer-success-fte"
REGISTRY="${REGISTRY:-docker.io/nimbusflow}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
DOMAIN="${DOMAIN:-api.nimbusflow.io}"
K8S_DIR="production/k8s"

SECRETS_ONLY=false
SKIP_BUILD=false
SKIP_INFRA=false
DRY_RUN=false
ENV_NAME="production"

# ── Parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --secrets-only) SECRETS_ONLY=true ;;
    --skip-build)   SKIP_BUILD=true ;;
    --skip-infra)   SKIP_INFRA=true ;;
    --dry-run)      DRY_RUN=true ;;
    --env)          ENV_NAME="$2"; shift ;;
    --tag)          IMAGE_TAG="$2"; shift ;;
    --namespace)    NAMESPACE="$2"; shift ;;
    --help|-h)
      grep '^#' "$0" | sed 's/^# \?//' | head -20
      exit 0
      ;;
    *) die "Unknown argument: $1 (use --help)" ;;
  esac
  shift
done

KUBECTL="kubectl"
[[ "$DRY_RUN" == "true" ]] && KUBECTL="kubectl --dry-run=client"

# ── Load .env if present ─────────────────────────────────────────────────────
if [[ -f ".env" ]]; then
  info "Loading .env"
  set -o allexport
  source .env
  set +o allexport
fi

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════╗"
echo "║  NimbusFlow Customer Success FTE — Deploy        ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Namespace : $NAMESPACE"
echo "  Image     : $REGISTRY/customer-success-fte:$IMAGE_TAG"
echo "  Domain    : $DOMAIN"
echo "  Dry run   : $DRY_RUN"
echo ""

# ════════════════════════════════════════════════════════════════════════════
# STEP 0: Prerequisite checks
# ════════════════════════════════════════════════════════════════════════════
step "Checking prerequisites"

check_tool() {
  if ! command -v "$1" &>/dev/null; then
    die "$1 is not installed. See docs/deployment-guide.md for install instructions."
  fi
  success "$1 found: $(command -v $1)"
}

check_tool kubectl
check_tool docker

# Verify cluster connectivity
if ! kubectl cluster-info &>/dev/null; then
  die "kubectl cannot reach the cluster. Check your kubeconfig:\n  kubectl cluster-info"
fi
success "Cluster reachable: $(kubectl config current-context)"

# Verify namespace exists (or create it)
if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
  info "Namespace $NAMESPACE not found — creating it"
  kubectl apply -f "$K8S_DIR/namespace.yaml"
fi
success "Namespace: $NAMESPACE"

# ════════════════════════════════════════════════════════════════════════════
# STEP 1: Validate required environment variables
# ════════════════════════════════════════════════════════════════════════════
step "Validating environment variables"

validate_var() {
  local var_name="$1"
  local value="${!var_name:-}"
  if [[ -z "$value" ]] || [[ "$value" == *"REPLACE"* ]] || [[ "$value" == *"..."* ]]; then
    die "$var_name is not set or still has a placeholder value.\n  See docs/environment-setup.md"
  fi
  # Mask secrets in output
  local display="${value:0:8}..."
  success "$var_name = $display"
}

validate_var GEMINI_API_KEY
validate_var POSTGRES_PASSWORD
validate_var TWILIO_ACCOUNT_SID
validate_var TWILIO_AUTH_TOKEN

# OpenAI is optional but warn
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  warn "OPENAI_API_KEY not set — knowledge base embedding search will not work"
fi

# Gmail credentials
if [[ ! -f "secrets/gmail_credentials.json" ]]; then
  warn "secrets/gmail_credentials.json not found — email channel will be unconfigured"
  warn "See docs/environment-setup.md Section 4 for Gmail setup"
  GMAIL_OK=false
else
  success "secrets/gmail_credentials.json found"
  GMAIL_OK=true
fi

if [[ ! -f "secrets/gmail_token.json" ]]; then
  warn "secrets/gmail_token.json not found — email channel will be unconfigured"
  GMAIL_OK=false
else
  success "secrets/gmail_token.json found"
fi

# If --secrets-only, jump straight to secret application
if [[ "$SECRETS_ONLY" == "true" ]]; then
  step "Applying secrets only"
  apply_secrets
  success "Secrets applied. Run without --secrets-only for full deployment."
  exit 0
fi

# ════════════════════════════════════════════════════════════════════════════
# STEP 2: Build and push Docker image
# ════════════════════════════════════════════════════════════════════════════
if [[ "$SKIP_BUILD" == "false" ]]; then
  step "Building Docker image"

  IMAGE_FULL="$REGISTRY/customer-success-fte:$IMAGE_TAG"
  IMAGE_LATEST="$REGISTRY/customer-success-fte:latest"

  docker build \
    --target production \
    --tag "$IMAGE_FULL" \
    --tag "$IMAGE_LATEST" \
    --label "build.git-sha=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)" \
    --label "build.timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    .

  success "Image built: $IMAGE_FULL"

  # Smoke test the image
  info "Running import smoke test..."
  docker run --rm "$IMAGE_FULL" \
    python -c "from production.api.main import app; print('import ok')" \
    || die "Image import test failed — do not push a broken image"
  success "Image smoke test passed"

  info "Pushing $IMAGE_FULL..."
  docker push "$IMAGE_FULL"
  docker push "$IMAGE_LATEST"
  success "Image pushed"
else
  info "Skipping image build (--skip-build)"
fi

# ════════════════════════════════════════════════════════════════════════════
# STEP 3: Check infrastructure prerequisites
# ════════════════════════════════════════════════════════════════════════════
if [[ "$SKIP_INFRA" == "false" ]]; then
  step "Checking infrastructure"

  # nginx-ingress
  if kubectl get deployment ingress-nginx-controller -n ingress-nginx &>/dev/null; then
    success "nginx-ingress: installed"
  else
    warn "nginx-ingress not found. Run:"
    warn "  kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml"
  fi

  # cert-manager
  if kubectl get deployment cert-manager -n cert-manager &>/dev/null; then
    success "cert-manager: installed"
    if kubectl get clusterissuer letsencrypt-prod &>/dev/null; then
      success "ClusterIssuer letsencrypt-prod: exists"
    else
      warn "ClusterIssuer letsencrypt-prod not found. Create it before TLS will work."
      warn "See docs/deployment-guide.md Section 2b"
    fi
  else
    warn "cert-manager not found. TLS will not work without it."
  fi

  # metrics-server (for HPA)
  if kubectl top nodes &>/dev/null 2>&1; then
    success "metrics-server: running"
  else
    warn "metrics-server not responding — HPA will not scale. Run:"
    warn "  kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml"
  fi
fi

# ════════════════════════════════════════════════════════════════════════════
# STEP 4: Apply secrets
# ════════════════════════════════════════════════════════════════════════════
apply_secrets() {
  step "Applying Kubernetes secrets"

  # fte-secrets (API keys + DB password)
  kubectl create secret generic fte-secrets \
    --namespace "$NAMESPACE" \
    --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
    --from-literal=GEMINI_API_KEY="${GEMINI_API_KEY}" \
    --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY:-placeholder}" \
    --from-literal=TWILIO_ACCOUNT_SID="${TWILIO_ACCOUNT_SID}" \
    --from-literal=TWILIO_AUTH_TOKEN="${TWILIO_AUTH_TOKEN}" \
    --dry-run=client -o yaml | $KUBECTL apply -f -
  success "fte-secrets applied"

  # fte-gmail-secrets (file-mounted OAuth2 credentials)
  if [[ "${GMAIL_OK:-false}" == "true" ]]; then
    kubectl create secret generic fte-gmail-secrets \
      --namespace "$NAMESPACE" \
      --from-file=gmail_credentials.json=secrets/gmail_credentials.json \
      --from-file=gmail_token.json=secrets/gmail_token.json \
      --dry-run=client -o yaml | $KUBECTL apply -f -
    success "fte-gmail-secrets applied"
  else
    # Create empty Gmail secret so pods can start (channel will be unconfigured)
    kubectl create secret generic fte-gmail-secrets \
      --namespace "$NAMESPACE" \
      --from-literal=gmail_credentials.json='{}' \
      --from-literal=gmail_token.json='{}' \
      --dry-run=client -o yaml | $KUBECTL apply -f - 2>/dev/null || true
    warn "fte-gmail-secrets created with empty placeholders (email channel unconfigured)"
  fi
}

apply_secrets

# ════════════════════════════════════════════════════════════════════════════
# STEP 5: Update domain in ingress.yaml
# ════════════════════════════════════════════════════════════════════════════
step "Configuring domain"

if grep -q "api.nimbusflow.io" "$K8S_DIR/ingress.yaml"; then
  if [[ "$DOMAIN" != "api.nimbusflow.io" ]]; then
    sed -i "s/api.nimbusflow.io/$DOMAIN/g" "$K8S_DIR/ingress.yaml"
    success "Domain updated to $DOMAIN in ingress.yaml"
  else
    info "Using default domain: api.nimbusflow.io"
  fi
fi

# ════════════════════════════════════════════════════════════════════════════
# STEP 6: Apply Kubernetes manifests in dependency order
# ════════════════════════════════════════════════════════════════════════════
step "Applying Kubernetes manifests"

apply() {
  local file="$1"
  local name="${file##*/}"
  info "Applying $name..."
  $KUBECTL apply -f "$file"
  success "$name applied"
}

apply "$K8S_DIR/namespace.yaml"
apply "$K8S_DIR/configmap.yaml"
# Secrets already applied in step 4
apply "$K8S_DIR/service.yaml"
apply "$K8S_DIR/deployment-api.yaml"
apply "$K8S_DIR/deployment-worker.yaml"
apply "$K8S_DIR/ingress.yaml"
apply "$K8S_DIR/hpa.yaml"

# Monitoring — only apply if Prometheus Operator CRDs exist
if kubectl api-resources | grep -q "servicemonitors.monitoring.coreos.com" 2>/dev/null; then
  apply "$K8S_DIR/monitoring.yaml"
else
  warn "Prometheus Operator CRDs not found — skipping monitoring.yaml"
  warn "Install kube-prometheus-stack to enable alerts"
fi

# ════════════════════════════════════════════════════════════════════════════
# STEP 7: Wait for rollout
# ════════════════════════════════════════════════════════════════════════════
if [[ "$DRY_RUN" == "false" ]]; then
  step "Waiting for rollout"

  info "Waiting for fte-api rollout..."
  kubectl rollout status deployment/fte-api \
    --namespace "$NAMESPACE" \
    --timeout=300s \
    || die "fte-api rollout timed out. Check: kubectl describe pods -l app=fte-api -n $NAMESPACE"
  success "fte-api rollout complete"

  info "Waiting for fte-worker rollout..."
  kubectl rollout status deployment/fte-worker \
    --namespace "$NAMESPACE" \
    --timeout=300s \
    || die "fte-worker rollout timed out. Check: kubectl describe pods -l app=fte-worker -n $NAMESPACE"
  success "fte-worker rollout complete"
fi

# ════════════════════════════════════════════════════════════════════════════
# STEP 8: Verify deployment
# ════════════════════════════════════════════════════════════════════════════
if [[ "$DRY_RUN" == "false" ]]; then
  step "Verifying deployment"

  # Pod count
  API_PODS=$(kubectl get pods -n "$NAMESPACE" -l app=fte-api \
    --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')
  WORKER_PODS=$(kubectl get pods -n "$NAMESPACE" -l app=fte-worker \
    --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')

  [[ "$API_PODS" -ge 3 ]] && success "API pods running: $API_PODS" \
    || warn "Only $API_PODS API pods running (expected 3)"
  [[ "$WORKER_PODS" -ge 3 ]] && success "Worker pods running: $WORKER_PODS" \
    || warn "Only $WORKER_PODS worker pods running (expected 3)"

  # Health check via port-forward (non-blocking)
  info "Testing health endpoint via port-forward..."
  kubectl port-forward svc/fte-api "$NAMESPACE" 18000:80 &>/dev/null &
  PF_PID=$!
  sleep 3

  if curl -sf http://localhost:18000/health > /dev/null 2>&1; then
    HEALTH=$(curl -s http://localhost:18000/health)
    STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
    [[ "$STATUS" == "ok" ]] && success "Health check: $STATUS" || warn "Health check returned: $STATUS"
  else
    warn "Health endpoint not responding via port-forward (may need more time to start)"
  fi

  kill $PF_PID 2>/dev/null || true
fi

# ════════════════════════════════════════════════════════════════════════════
# DONE
# ════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${GREEN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅  Deployment Complete                          ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Namespace : $NAMESPACE"
echo "  API URL   : https://$DOMAIN"
echo ""
echo "  Next steps:"
echo "    1. Run: ./scripts/test-deployment.sh"
echo "    2. Open Grafana: kubectl port-forward svc/kube-prometheus-grafana -n monitoring 3000:80"
echo "    3. Import dashboard: docs/grafana-dashboard.json"
echo ""
echo "  Useful commands:"
echo "    kubectl get pods -n $NAMESPACE"
echo "    kubectl logs -l app=fte-api -n $NAMESPACE -f"
echo "    kubectl logs -l app=fte-worker -n $NAMESPACE -f"
