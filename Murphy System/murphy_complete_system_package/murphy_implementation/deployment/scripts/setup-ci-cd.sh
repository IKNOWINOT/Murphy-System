#!/bin/bash

# CI/CD Pipeline Setup Script
# Sets up GitHub Actions / GitLab CI for Murphy System

set -e

echo "=========================================="
echo "Murphy System CI/CD Setup"
echo "=========================================="

# Create GitHub Actions workflow
create_github_actions() {
    mkdir -p .github/workflows
    
    cat > .github/workflows/murphy-ci-cd.yml << 'EOF'
name: Murphy System CI/CD

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        pytest tests/ --cov=murphy_implementation --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
    - uses: actions/checkout@v3
    
    - name: Log in to Container Registry
      uses: docker/login-action@v2
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v4
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
    
    - name: Build and push Docker image
      uses: docker/build-push-action@v4
      with:
        context: .
        file: murphy_implementation/deployment/Dockerfile
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to Staging
      run: |
        echo "Deploying to staging environment..."
        # Add staging deployment commands here

  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to Production
      run: |
        echo "Deploying to production environment..."
        # Add production deployment commands here
EOF
    
    echo "GitHub Actions workflow created at .github/workflows/murphy-ci-cd.yml"
}

# Create GitLab CI configuration
create_gitlab_ci() {
    cat > .gitlab-ci.yml << 'EOF'
stages:
  - test
  - build
  - deploy

variables:
  DOCKER_DRIVER: overlay2
  DOCKER_TLS_CERTDIR: "/certs"

test:
  stage: test
  image: python:3.11
  script:
    - pip install -r requirements.txt
    - pip install pytest pytest-cov
    - pytest tests/ --cov=murphy_implementation --cov-report=xml
  coverage: '/(?i)total.*? (100(?:\.0+)?\%|[1-9]?\d(?:\.\d+)?\%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA -f murphy_implementation/deployment/Dockerfile .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  only:
    - main
    - develop

deploy-staging:
  stage: deploy
  script:
    - echo "Deploying to staging..."
    # Add staging deployment commands
  environment:
    name: staging
  only:
    - develop

deploy-production:
  stage: deploy
  script:
    - echo "Deploying to production..."
    # Add production deployment commands
  environment:
    name: production
  when: manual
  only:
    - main
EOF
    
    echo "GitLab CI configuration created at .gitlab-ci.yml"
}

# Main
echo "Select CI/CD platform:"
echo "1) GitHub Actions"
echo "2) GitLab CI"
echo "3) Both"
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        create_github_actions
        ;;
    2)
        create_gitlab_ci
        ;;
    3)
        create_github_actions
        create_gitlab_ci
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo "=========================================="
echo "CI/CD setup completed!"
echo "=========================================="