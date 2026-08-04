# Day 9 — Prometheus Alerting and Alertmanager Routing

## Objective

Deploy Alertmanager, connect it with Prometheus, validate alert rules, and test
the complete alert lifecycle in the Kubernetes lab.

## Environment

| Component | Value |
|---|---|
| Kubernetes | v1.30.14 |
| Nodes | k8s-master, k8s-worker01, k8s-worker02 |
| Networking | Calico |
| Monitoring | Prometheus and Grafana |
| Alert routing | Alertmanager v0.33.1 |

## Architecture

    Kubernetes health reporter
              |
              v
          Prometheus
              |
         Alert rules
              |
              v
         Alertmanager
              |
              v
       lab-console receiver

## Added manifests

- `kubernetes/monitoring/11-alertmanager-config.yaml`
- `kubernetes/monitoring/12-alertmanager-deployment.yaml`
- `kubernetes/monitoring/13-alertmanager-service.yaml`

The existing `01-prometheus-config.yaml` was updated to connect Prometheus to:

    alertmanager.monitoring.svc.cluster.local:9093

## Alert rules

| Alert | Condition | Duration | Severity |
|---|---|---:|---|
| KubernetesHealthReporterTargetDown | Target up value is 0 | 2 minutes | Critical |
| KubernetesHealthReporterJobFailed | Reporter exit code is non-zero | 5 minutes | Critical |
| KubernetesNodesNotReady | Ready nodes are fewer than total | 5 minutes | Warning |
| KubernetesUnhealthyPodsDetected | Unhealthy pod count is above zero | 5 minutes | Warning |

## Configuration validation

Alertmanager configuration was validated with:

    amtool check-config /etc/alertmanager/alertmanager.yml

Result:

    SUCCESS
    1 receiver
    0 inhibit rules

Prometheus configuration and rules were validated with:

    promtool check config /etc/prometheus/prometheus.yml
    promtool check rules /etc/prometheus/rules/health-reporter-alerts.yaml

Result:

    SUCCESS: 1 rule file found
    SUCCESS: 4 rules found

## Prometheus and Alertmanager connectivity

Prometheus reported one active Alertmanager:

    http://alertmanager.monitoring.svc.cluster.local:9093/api/v2/alerts

No dropped Alertmanager endpoint was reported.

## Controlled alert test

The health-reporter metrics Deployment was temporarily scaled down:

    kubectl scale deployment health-reporter-metrics \
      -n ai-infrastructure \
      --replicas=0

The following lifecycle was observed:

1. The metrics Service endpoint became empty.
2. The Prometheus `up` metric changed from 1 to 0.
3. The alert entered the pending state.
4. After two minutes, the alert entered the firing state.
5. Prometheus sent the alert to Alertmanager.
6. Alertmanager routed it to the `lab-console` receiver.

Alert labels included:

    alertname: KubernetesHealthReporterTargetDown
    cluster: ai-infrastructure-lab
    component: health-reporter
    severity: critical
    state: active

## Recovery

The health reporter was restored:

    kubectl scale deployment health-reporter-metrics \
      -n ai-infrastructure \
      --replicas=1

After recovery:

- The Deployment returned to 1/1.
- The metrics endpoint returned.
- The Prometheus `up` metric returned to 1.
- The alert condition cleared.

## Image reproducibility

Alertmanager was pinned to the immutable image digest:

    docker.io/prom/alertmanager@sha256:9e082985f56f4c8c9f724e18f2288c6708f472e56a5286b8863d080434ea065d

## Learning

A shell variable created in one terminal is not available in another terminal.
For safe automation, capture and restore the original replica count within the
same script or shell session.

Prometheus detects and evaluates alert conditions. Alertmanager receives firing
alerts, groups and deduplicates them, applies routing and inhibition rules, and
delivers them to configured receivers.

## Production improvements

- Multiple Alertmanager replicas
- Persistent storage for silences
- Email, Teams, Slack or PagerDuty receivers
- Credentials stored in Kubernetes Secrets
- TLS, authentication and NetworkPolicies
- kube-state-metrics and node-exporter
- Inhibition rules and runbook URLs
- Automated configuration reload
