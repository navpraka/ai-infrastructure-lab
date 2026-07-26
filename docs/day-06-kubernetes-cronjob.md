# Day 6 - Kubernetes-Native Health Reporter

Date: 26 July 2026

## Objective

Publish the Kubernetes Health Reporter container to GitHub Container
Registry and deploy it as a secure, scheduled Kubernetes workload.

## Architecture

```text
GitHub Actions
    |
    v
GitHub Container Registry
    |
    v
Kubernetes CronJob
    |
    +-- ServiceAccount
    +-- Read-only ClusterRole
    +-- PersistentVolumeClaim
    +-- Kubernetes API
```

## Container Registry

```text
ghcr.io/navpraka/ai-infrastructure-lab/kubernetes-health-reporter
```

The image is published automatically after successful tests and container
validation on the main branch.

The Kubernetes deployment uses an immutable SHA256 image digest instead
of the mutable `latest` tag.

## Kubernetes Resources

```text
Namespace:          ai-infrastructure
ServiceAccount:     health-reporter
ClusterRole:        health-reporter-reader
ClusterRoleBinding: health-reporter-reader
CronJob:            kubernetes-health-reporter
StorageClass:       local-storage
PersistentVolume:   health-reporter-pv
PersistentVolumeClaim: health-reporter-output
```

## RBAC

The ServiceAccount can read:

- Nodes
- Namespaces
- Pods
- Events
- Kubernetes version information

The ServiceAccount cannot create, update, patch, or delete Kubernetes
resources.

## Container Security

- Runs as non-root UID and GID 10001
- Privilege escalation is disabled
- Linux capabilities are dropped
- Root filesystem is read-only
- RuntimeDefault seccomp profile is enabled
- CPU and memory requests and limits are configured
- Kubernetes credentials use a projected ServiceAccount token

## Scheduling

```text
Schedule: */15 * * * *
Concurrency policy: Forbid
Maximum runtime: 300 seconds
```

The reporter executes every 15 minutes. Concurrent executions are not
allowed.

## Persistent Storage

The lab cluster does not currently have a CSI dynamic provisioner.
A static local PersistentVolume was therefore created on k8s-worker01.

```text
Path: /var/lib/ai-infrastructure-lab/health-reporter
Capacity: 1Gi
Access mode: ReadWriteOnce
Reclaim policy: Retain
```

This local volume is suitable for the lab but is not highly available.
A production deployment should use CSI-backed shared or replicated
storage such as Ceph, NFS, or cloud block storage.

## Validation Results

```text
GitHub Container Registry pull: Successful
Manual Kubernetes Job: Complete
Automatic CronJob execution: Complete
Application exit code: 0
Cluster status: HEALTHY
Ready nodes: 3/3
PersistentVolumeClaim: Bound
Scheduled pod node: k8s-worker01
Unit and policy tests: 25 passed
```

## Automated Policy Tests

The manifest tests validate:

- Required Kubernetes metadata
- Unique resource identities
- Read-only RBAC permissions
- Immutable SHA256 image reference
- Non-root container execution
- Disabled privilege escalation
- Read-only root filesystem
- Dropped Linux capabilities
- PersistentVolume Retain policy
- CronJob concurrency policy and schedule

## Result

The Health Reporter now operates as a secure Kubernetes-native scheduled
workload with automated image publication, least-privilege access,
persistent report storage, and CI policy validation.
