# Day 7 - Prometheus Monitoring and Custom Metrics

Date: 26 July 2026

## Objective

Add Prometheus-compatible metrics to the Kubernetes Health Reporter,
expose those metrics inside Kubernetes, and deploy a secure Prometheus
instance to collect and retain them.

## Architecture

The Kubernetes Health Reporter runs as a CronJob every 15 minutes.

Each execution writes three report formats to persistent storage:

- JSON report
- Human-readable text report
- Prometheus text exposition report

A dedicated metrics Deployment mounts the report volume as read-only
and exposes the Prometheus report through an internal ClusterIP Service.

Prometheus scrapes this Service every 15 seconds and stores the collected
time-series data on a persistent local volume.

## Metrics Pipeline

```text
Kubernetes API
    |
Health Reporter CronJob
    |
Report PVC on k8s-worker01
    |
Metrics HTTP Deployment
    |
health-reporter-metrics Service
    |
Prometheus on k8s-worker02
    |
Prometheus persistent storage
