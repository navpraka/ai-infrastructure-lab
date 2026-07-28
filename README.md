# AI Infrastructure Lab

## Overview

This repository documents my hands-on journey toward becoming an AI Infrastructure Architect.

The lab focuses on designing, deploying, automating, monitoring, and troubleshooting production-grade infrastructure.

## Core Technologies

- Kubernetes
- OpenShift
- OpenStack
- Docker
- Linux
- Python
- Git and GitHub
- Terraform
- Ansible
- AI Infrastructure
- MLOps
- LLM Deployment

## Lab Environment

| Component | Status |
|---|---|
| Three-node Kubernetes cluster | Running |
| Docker Desktop | Installed |
| WSL 2 Ubuntu | Installed |
| Python | Installed |
| Git | Installed |
| VS Code | Installed |

## Projects

### Project 1: Environment Reporter

A Python utility that reports:

- Hostname
- Operating system
- CPU architecture
- Python version
- Current user
- Disk capacity and usage

Run:

```bash
python3 python/automation/environment_report.py

```

### Project 4: Kubernetes Monitoring, Grafana, and Alerting

Implemented a Git-managed monitoring stack for the Kubernetes health reporter:

- Prometheus metrics scraping and seven-day local retention
- Prometheus alert rules for reporter, node, and pod health
- Grafana deployment with a provisioned Prometheus datasource
- Kubernetes health dashboard provisioned automatically from ConfigMaps
- Secure Grafana admin password stored in a Kubernetes Secret, not Git
- Troubleshooting runbook for Calico CNI authentication failures

See [Day 8 documentation](docs/day-08-grafana-prometheus-alerting.md).