#!/bin/bash

# Murphy System Deployment Script
# Usage: ./deploy.sh [environment] [version]

set -e

ENVIRONMENT=${1:-production}
VERSION=${2:-latest}
NAMESPACE="murphy-system"

echo "=========================================="
echo "Murphy System Deployment"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Version: $VERSION"
echo "Namespace: $NAMESPACE"
echo "=========================================="

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        log_error "docker not found. Please install docker."
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Build Docker image
build_image() {
    log_info "Building Docker image..."
    
    cd ../..
    docker build -t murphy-system:$VERSION -f murphy_implementation/deployment/Dockerfile .
    
    if [ $? -eq 0 ]; then
        log_info "Docker image built successfully"
    else
        log_error "Docker image build failed"
        exit 1
    fi
}

# Push Docker image
push_image() {
    log_info "Pushing Docker image to registry..."
    
    # Tag for registry
    docker tag murphy-system:$VERSION your-registry.com/murphy-system:$VERSION
    
    # Push to registry
    docker push your-registry.com/murphy-system:$VERSION
    
    if [ $? -eq 0 ]; then
        log_info "Docker image pushed successfully"
    else
        log_error "Docker image push failed"
        exit 1
    fi
}

# Create namespace
create_namespace() {
    log_info "Creating namespace..."
    
    kubectl apply -f kubernetes/namespace.yaml
    
    if [ $? -eq 0 ]; then
        log_info "Namespace created/updated successfully"
    else
        log_error "Namespace creation failed"
        exit 1
    fi
}

# Deploy to Kubernetes
deploy_kubernetes() {
    log_info "Deploying to Kubernetes..."
    
    # Apply deployment
    kubectl apply -f kubernetes/deployment.yaml -n $NAMESPACE
    
    if [ $? -eq 0 ]; then
        log_info "Deployment applied successfully"
    else
        log_error "Deployment failed"
        exit 1
    fi
    
    # Wait for rollout
    log_info "Waiting for rollout to complete..."
    kubectl rollout status deployment/murphy-api -n $NAMESPACE --timeout=5m
    
    if [ $? -eq 0 ]; then
        log_info "Rollout completed successfully"
    else
        log_error "Rollout failed"
        exit 1
    fi
}

# Run health checks
health_check() {
    log_info "Running health checks..."
    
    # Get service endpoint
    SERVICE_IP=$(kubectl get svc murphy-api-service -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    
    if [ -z "$SERVICE_IP" ]; then
        log_warn "Service IP not available yet. Skipping health check."
        return
    fi
    
    # Check health endpoint
    HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://$SERVICE_IP/health)
    
    if [ "$HEALTH_STATUS" == "200" ]; then
        log_info "Health check passed"
    else
        log_error "Health check failed (HTTP $HEALTH_STATUS)"
        exit 1
    fi
}

# Rollback deployment
rollback() {
    log_warn "Rolling back deployment..."
    
    kubectl rollout undo deployment/murphy-api -n $NAMESPACE
    
    if [ $? -eq 0 ]; then
        log_info "Rollback completed successfully"
    else
        log_error "Rollback failed"
        exit 1
    fi
}

# Main deployment flow
main() {
    check_prerequisites
    
    # Build and push image
    build_image
    
    if [ "$ENVIRONMENT" == "production" ]; then
        push_image
    fi
    
    # Deploy to Kubernetes
    create_namespace
    deploy_kubernetes
    
    # Run health checks
    sleep 10
    health_check
    
    log_info "=========================================="
    log_info "Deployment completed successfully!"
    log_info "=========================================="
    
    # Show deployment info
    kubectl get pods -n $NAMESPACE
    kubectl get svc -n $NAMESPACE
}

# Handle errors
trap 'log_error "Deployment failed. Run ./deploy.sh rollback to revert."; exit 1' ERR

# Run deployment
if [ "$1" == "rollback" ]; then
    rollback
else
    main
fi