# AI Hedge Fund Helm Chart

This Helm chart deploys the AI Hedge Fund application on a Kubernetes cluster.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PV provisioner support in the underlying infrastructure (if persistence is enabled)
- Ingress controller (if ingress is enabled)

## Installing the Chart

To install the chart with the release name `my-release`:

```bash
# Add the repository (if hosted in a Helm repository)
# helm repo add ai-hedge-fund https://ai-hedge-fund-repo.example.com
# helm repo update

# Install the chart
helm install my-release ./charts/ai-hedge-fund
```

The command deploys AI Hedge Fund on the Kubernetes cluster with default configuration. The [Parameters](#parameters) section lists the parameters that can be configured during installation.

## Uninstalling the Chart

To uninstall/delete the `my-release` deployment:

```bash
helm uninstall my-release
```

## Parameters

### Global parameters

| Name                      | Description                                     | Value       |
| ------------------------- | ----------------------------------------------- | ----------- |
| `global.environment`      | Environment (production, staging, development)  | `production` |

### Backend parameters

| Name                                        | Description                                                                             | Value           |
| ------------------------------------------- | --------------------------------------------------------------------------------------- | --------------- |
| `backend.name`                              | Name of the backend deployment                                                          | `ai-hedge-fund-backend` |
| `backend.replicaCount`                      | Number of backend replicas                                                              | `1`             |
| `backend.image.repository`                  | Backend image repository                                                                | `ai-hedge-fund/backend` |
| `backend.image.tag`                         | Backend image tag                                                                       | `latest`        |
| `backend.image.pullPolicy`                  | Backend image pull policy                                                               | `IfNotPresent`  |
| `backend.resources.limits.cpu`              | Backend CPU limit                                                                       | `1000m`         |
| `backend.resources.limits.memory`           | Backend memory limit                                                                    | `2Gi`           |
| `backend.resources.requests.cpu`            | Backend CPU request                                                                     | `500m`          |
| `backend.resources.requests.memory`         | Backend memory request                                                                  | `1Gi`           |
| `backend.service.type`                      | Backend service type                                                                    | `ClusterIP`     |
| `backend.service.port`                      | Backend service port                                                                    | `8000`          |
| `backend.autoscaling.enabled`               | Enable autoscaling for backend                                                          | `false`         |
| `backend.autoscaling.minReplicas`           | Minimum number of backend replicas                                                      | `1`             |
| `backend.autoscaling.maxReplicas`           | Maximum number of backend replicas                                                      | `5`             |
| `backend.autoscaling.targetCPUUtilizationPercentage` | Target CPU utilization percentage for backend autoscaling                      | `80`            |
| `backend.env`                               | Environment variables for backend                                                       | `[]`            |
| `backend.envFrom`                           | Environment variables from secrets or configmaps                                        | `[]`            |
| `backend.livenessProbe`                     | Liveness probe configuration for backend                                                | See values.yaml |
| `backend.readinessProbe`                    | Readiness probe configuration for backend                                               | See values.yaml |

### Frontend parameters

| Name                                        | Description                                                                             | Value           |
| ------------------------------------------- | --------------------------------------------------------------------------------------- | --------------- |
| `frontend.name`                             | Name of the frontend deployment                                                         | `ai-hedge-fund-frontend` |
| `frontend.replicaCount`                     | Number of frontend replicas                                                             | `1`             |
| `frontend.image.repository`                 | Frontend image repository                                                               | `ai-hedge-fund/frontend` |
| `frontend.image.tag`                        | Frontend image tag                                                                      | `latest`        |
| `frontend.image.pullPolicy`                 | Frontend image pull policy                                                              | `IfNotPresent`  |
| `frontend.resources.limits.cpu`             | Frontend CPU limit                                                                      | `500m`          |
| `frontend.resources.limits.memory`          | Frontend memory limit                                                                   | `512Mi`         |
| `frontend.resources.requests.cpu`           | Frontend CPU request                                                                    | `200m`          |
| `frontend.resources.requests.memory`        | Frontend memory request                                                                 | `256Mi`         |
| `frontend.service.type`                     | Frontend service type                                                                   | `ClusterIP`     |
| `frontend.service.port`                     | Frontend service port                                                                   | `80`            |
| `frontend.autoscaling.enabled`              | Enable autoscaling for frontend                                                         | `false`         |
| `frontend.autoscaling.minReplicas`          | Minimum number of frontend replicas                                                     | `1`             |
| `frontend.autoscaling.maxReplicas`          | Maximum number of frontend replicas                                                     | `5`             |
| `frontend.autoscaling.targetCPUUtilizationPercentage` | Target CPU utilization percentage for frontend autoscaling                    | `80`            |
| `frontend.env`                              | Environment variables for frontend                                                      | `[]`            |
| `frontend.livenessProbe`                    | Liveness probe configuration for frontend                                               | See values.yaml |
| `frontend.readinessProbe`                   | Readiness probe configuration for frontend                                              | See values.yaml |

### Ingress parameters

| Name                        | Description                                                                             | Value                    |
| --------------------------- | --------------------------------------------------------------------------------------- | ------------------------ |
| `ingress.enabled`           | Enable ingress                                                                          | `true`                   |
| `ingress.className`         | Ingress class name                                                                      | `nginx`                  |
| `ingress.annotations`       | Ingress annotations                                                                     | See values.yaml          |
| `ingress.hosts`             | Ingress hosts configuration                                                             | See values.yaml          |
| `ingress.tls`               | Ingress TLS configuration                                                               | See values.yaml          |

### Persistence parameters

| Name                        | Description                                                                             | Value                    |
| --------------------------- | --------------------------------------------------------------------------------------- | ------------------------ |
| `persistence.enabled`       | Enable persistence                                                                      | `true`                   |
| `persistence.storageClass`  | Storage class for PVC                                                                   | `standard`               |
| `persistence.size`          | Size of PVC                                                                             | `10Gi`                   |
| `persistence.accessMode`    | Access mode for PVC                                                                     | `ReadWriteOnce`          |

### Secret parameters

| Name                        | Description                                                                             | Value                    |
| --------------------------- | --------------------------------------------------------------------------------------- | ------------------------ |
| `secrets.create`            | Create secrets                                                                          | `true`                   |
| `secrets.data`              | Secret data                                                                             | See values.yaml          |

### Redis parameters

| Name                        | Description                                                                             | Value                    |
| --------------------------- | --------------------------------------------------------------------------------------- | ------------------------ |
| `redis.enabled`             | Enable Redis                                                                            | `true`                   |
| `redis.architecture`        | Redis architecture                                                                      | `standalone`             |
| `redis.auth.enabled`        | Enable Redis authentication                                                             | `true`                   |
| `redis.auth.password`       | Redis password                                                                          | `""`                     |
| `redis.master.persistence.enabled` | Enable Redis persistence                                                         | `true`                   |
| `redis.master.persistence.size` | Redis persistence size                                                              | `8Gi`                    |

### Monitoring parameters

| Name                                | Description                                                                             | Value                    |
| ----------------------------------- | --------------------------------------------------------------------------------------- | ------------------------ |
| `monitoring.enabled`                | Enable monitoring                                                                       | `true`                   |
| `monitoring.serviceMonitor.enabled` | Enable service monitor                                                                  | `true`                   |
| `monitoring.serviceMonitor.interval` | Service monitor interval                                                               | `30s`                    |
| `monitoring.serviceMonitor.scrapeTimeout` | Service monitor scrape timeout                                                    | `10s`                    |

### Network policy parameters

| Name                        | Description                                                                             | Value                    |
| --------------------------- | --------------------------------------------------------------------------------------- | ------------------------ |
| `networkPolicy.enabled`     | Enable network policy                                                                   | `false`                  |

## Configuration and Installation Details

### Using custom configuration

To use custom configuration, you can modify the values.yaml file or provide your own values file:

```bash
helm install my-release ./charts/ai-hedge-fund -f my-values.yaml
```

### Setting up API keys

The AI Hedge Fund application requires several API keys to function properly. You can set these in the `secrets.data` section of your values file:

```yaml
secrets:
  create: true
  data:
    OPENAI_API_KEY: "your-openai-api-key"
    GROQ_API_KEY: "your-groq-api-key"
    FINANCIAL_DATASETS_API_KEY: "your-financial-datasets-api-key"
```

### Persistence

The chart mounts a Persistent Volume for the backend to store data. You can disable this by setting `persistence.enabled` to `false`.

### Ingress

The chart comes with ingress support. You can enable it by setting `ingress.enabled` to `true` and configuring the ingress parameters.

### Monitoring

The chart includes a ServiceMonitor for Prometheus monitoring. You can enable it by setting `monitoring.enabled` and `monitoring.serviceMonitor.enabled` to `true`.

## Upgrading

### To 1.0.0

This is the first version of the chart, so there are no special upgrade notes.