# AI Hedge Fund Kubernetes Deployment Examples

This directory contains example files for deploying the AI Hedge Fund application to Kubernetes using the Helm chart.

## Dockerfiles

- `Dockerfile.backend`: Dockerfile for building the backend image
- `Dockerfile.frontend`: Dockerfile for building the frontend image
- `nginx.conf`: Nginx configuration for the frontend

## Building the Docker Images

To build the Docker images, run the following commands from the root of the repository:

```bash
# Build the backend image
docker build -t ai-hedge-fund/backend:latest -f charts/ai-hedge-fund/examples/Dockerfile.backend .

# Build the frontend image
docker build -t ai-hedge-fund/frontend:latest -f charts/ai-hedge-fund/examples/Dockerfile.frontend .
```

## Pushing the Docker Images to a Registry

```bash
# Tag the images
docker tag ai-hedge-fund/backend:latest your-registry.example.com/ai-hedge-fund/backend:latest
docker tag ai-hedge-fund/frontend:latest your-registry.example.com/ai-hedge-fund/frontend:latest

# Push the images
docker push your-registry.example.com/ai-hedge-fund/backend:latest
docker push your-registry.example.com/ai-hedge-fund/frontend:latest
```

## Deploying with Helm

After building and pushing the Docker images, you can deploy the application using Helm:

```bash
# Update the values.yaml file with your registry
helm install ai-hedge-fund ./charts/ai-hedge-fund \
  --set backend.image.repository=your-registry.example.com/ai-hedge-fund/backend \
  --set frontend.image.repository=your-registry.example.com/ai-hedge-fund/frontend
```

## Environment-Specific Deployments

You can use the environment-specific values files for different environments:

```bash
# Development
helm install ai-hedge-fund ./charts/ai-hedge-fund -f ./charts/ai-hedge-fund/values/development.yaml

# Staging
helm install ai-hedge-fund ./charts/ai-hedge-fund -f ./charts/ai-hedge-fund/values/staging.yaml

# Production
helm install ai-hedge-fund ./charts/ai-hedge-fund -f ./charts/ai-hedge-fund/values/production.yaml
```

## Setting API Keys

You need to set your API keys in the secrets. You can do this by creating a custom values file:

```yaml
# my-values.yaml
secrets:
  create: true
  data:
    OPENAI_API_KEY: "your-openai-api-key"
    GROQ_API_KEY: "your-groq-api-key"
    FINANCIAL_DATASETS_API_KEY: "your-financial-datasets-api-key"
```

Then deploy with:

```bash
helm install ai-hedge-fund ./charts/ai-hedge-fund -f my-values.yaml
```

## CI/CD Integration

For CI/CD integration, you can use the following steps:

1. Build and push Docker images in your CI/CD pipeline
2. Deploy using Helm in your CI/CD pipeline

Example GitHub Actions workflow:

```yaml
name: Deploy to Kubernetes

on:
  push:
    branches: [ main ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v1
      
      - name: Login to Container Registry
        uses: docker/login-action@v1
        with:
          registry: your-registry.example.com
          username: ${{ secrets.REGISTRY_USERNAME }}
          password: ${{ secrets.REGISTRY_PASSWORD }}
      
      - name: Build and push backend
        uses: docker/build-push-action@v2
        with:
          context: .
          file: ./charts/ai-hedge-fund/examples/Dockerfile.backend
          push: true
          tags: your-registry.example.com/ai-hedge-fund/backend:latest
      
      - name: Build and push frontend
        uses: docker/build-push-action@v2
        with:
          context: .
          file: ./charts/ai-hedge-fund/examples/Dockerfile.frontend
          push: true
          tags: your-registry.example.com/ai-hedge-fund/frontend:latest
      
      - name: Set up Helm
        uses: azure/setup-helm@v1
        with:
          version: 'v3.8.0'
      
      - name: Deploy to Kubernetes
        run: |
          echo "${{ secrets.KUBECONFIG }}" > kubeconfig
          export KUBECONFIG=./kubeconfig
          
          helm upgrade --install ai-hedge-fund ./charts/ai-hedge-fund \
            --set backend.image.repository=your-registry.example.com/ai-hedge-fund/backend \
            --set frontend.image.repository=your-registry.example.com/ai-hedge-fund/frontend \
            --set secrets.data.OPENAI_API_KEY="${{ secrets.OPENAI_API_KEY }}" \
            --set secrets.data.GROQ_API_KEY="${{ secrets.GROQ_API_KEY }}" \
            --set secrets.data.FINANCIAL_DATASETS_API_KEY="${{ secrets.FINANCIAL_DATASETS_API_KEY }}"
```