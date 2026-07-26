# Day 5 - Containerized Kubernetes Health Reporter

Date: 26 July 2026

## Objective

Package the Kubernetes Health Reporter as a secure container image and
validate it against the Kubernetes lab cluster.

## Components Added

- Dockerfile for the Kubernetes Health Reporter
- Python 3.12 container runtime
- kubectl v1.30.14
- SHA256 verification for the kubectl binary
- Non-root container user
- Docker build validation in GitHub Actions
- Docker build-context exclusions

## Files

```text
docker/kubernetes-health-reporter/Dockerfile
.dockerignore
.github/workflows/python-ci.yml
```

## Container Image

```text
ai-infrastructure-lab/kubernetes-health-reporter:v2
```

## Security Controls

- The kubectl binary is downloaded from dl.k8s.io.
- The kubectl SHA256 checksum is verified during the image build.
- The application runs as non-root UID 10001.
- Kubernetes credentials are not copied into the image.
- The kubeconfig is mounted read-only at runtime.
- Unnecessary repository files are excluded using .dockerignore.

## Local Validation

```text
Python version: 3.12.13
kubectl version: v1.30.14
Container user ID: 10001
Unit tests: 11 passed
```

## Kubernetes Cluster Validation

```text
API server: https://192.168.48.129:6443
Ready nodes: 3/3
Healthy pods: 21/21
Overall status: HEALTHY
Reporter exit code: 0
```

The container successfully connected to the Kubernetes API using a
temporary, read-only kubeconfig mount.

## CI Validation

GitHub Actions performs the following checks:

1. Installs the Python test dependencies.
2. validates the Python syntax.
3. Runs the unit tests.
4. Builds the container image.
5. Verifies the Python version inside the image.
6. Verifies the kubectl client inside the image.
7. Confirms that the image runs as non-root UID 10001.

## Result

The Kubernetes Health Reporter can now run consistently as a secure
containerized application. It is ready for Kubernetes RBAC and CronJob
deployment in the next phase.
