# AI Hedge Fund Kubernetes Deployment

This directory contains Helm charts for deploying the AI Hedge Fund application to Kubernetes.

## Available Charts

- [ai-hedge-fund](./ai-hedge-fund/README.md): Helm chart for deploying the AI Hedge Fund application

## Quick Start

To deploy the AI Hedge Fund application to Kubernetes:

1. Build and push Docker images (see [examples](./ai-hedge-fund/examples/README.md))
2. Install the Helm chart:

```bash
helm install ai-hedge-fund ./ai-hedge-fund
```

## Environment-Specific Deployments

You can use the environment-specific values files for different environments:

```bash
# Development
helm install ai-hedge-fund ./ai-hedge-fund -f ./ai-hedge-fund/values/development.yaml

# Staging
helm install ai-hedge-fund ./ai-hedge-fund -f ./ai-hedge-fund/values/staging.yaml

# Production
helm install ai-hedge-fund ./ai-hedge-fund -f ./ai-hedge-fund/values/production.yaml
```

## Configuration

See the [ai-hedge-fund chart README](./ai-hedge-fund/README.md) for detailed configuration options.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PV provisioner support in the underlying infrastructure (if persistence is enabled)
- Ingress controller (if ingress is enabled)

## Contributing

If you'd like to contribute to the Helm charts, please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.