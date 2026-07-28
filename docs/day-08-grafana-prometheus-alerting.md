# Day 8: Grafana Dashboards and Prometheus Alerting

## Objective

Build a monitoring workflow for the Kubernetes health reporter:

```text
Kubernetes Health Reporter → Prometheus → Grafana Dashboard
                                  └────→ Alert Rules
Delivered Components
Component	Purpose
Prometheus alert rules	Detect health-reporter, node, and pod health failures
Grafana	Visualize health metrics from Prometheus
Provisioned datasource	Connect Grafana to the internal Prometheus service
Provisioned dashboard	Create the dashboard automatically from Git-managed configuration
Kubernetes Secret	Store the Grafana admin password outside Git
Prometheus Alert Rules
Alert	Condition	Severity
KubernetesHealthReporterTargetDown	Reporter metrics target is unavailable for 2 minutes	Critical
KubernetesHealthReporterJobFailed	Latest reporter exit code is non-zero for 5 minutes	Critical
KubernetesNodesNotReady	Ready node count is lower than total node count for 5 minutes	Warning
KubernetesUnhealthyPodsDetected	Unhealthy pod count is greater than zero for 5 minutes	Warning
Grafana Dashboard

Dashboard: Kubernetes Health Reporter

Panels:

Unhealthy Pods
Nodes Ready / Total
Healthy Pods / Total
Warning Events
Node Health Trend
Pod Health Trend

The dashboard is provisioned through ConfigMaps. This means a new Grafana pod automatically receives the datasource and dashboard without manual UI configuration.

Deployment

Create the Grafana password Secret locally. Do not commit this Secret to Git.

read -s -p "Choose Grafana admin password: " GRAFANA_ADMIN_PASSWORD
echo

kubectl create secret generic grafana-admin-credentials \
  -n monitoring \
  --from-literal=admin-password="$GRAFANA_ADMIN_PASSWORD" \
  --dry-run=client \
  -o yaml \
  | kubectl apply -f -

unset GRAFANA_ADMIN_PASSWORD

Deploy monitoring components:

kubectl apply \
  -f kubernetes/monitoring/06-prometheus-alert-rules.yaml \
  -f kubernetes/monitoring/07-grafana-provisioning.yaml \
  -f kubernetes/monitoring/08-grafana-dashboard.yaml \
  -f kubernetes/monitoring/09-grafana-deployment.yaml \
  -f kubernetes/monitoring/10-grafana-service.yaml
Validation

Verify Prometheus rules:

kubectl -n monitoring port-forward svc/prometheus 9090:9090
curl -s http://127.0.0.1:9090/api/v1/rules | python3 -m json.tool

Verify Grafana:

kubectl -n monitoring port-forward svc/grafana 3000:3000
curl -s http://127.0.0.1:3000/api/health | python3 -m json.tool

Open Grafana at http://127.0.0.1:3000 and sign in with user admin.

Troubleshooting Lesson: Calico CNI Unauthorized

During deployment, Prometheus and Grafana pods were blocked with:

plugin type="calico" failed:
error getting ClusterInformation: connection is unauthorized: Unauthorized

The application manifests were valid. The issue was Calico CNI authentication on the affected worker node, preventing kubelet from creating or removing pod sandboxes.

Lab recovery:

kubectl delete pod -n calico-system <calico-node-pod-on-affected-worker>

The DaemonSet recreated Calico, refreshed the CNI state, and Kubernetes successfully started the workload pod.

For production, collect Calico, kubelet, API server, certificate, and service-account-token evidence before restarting networking components. Treat it as a controlled maintenance action.

Result
Prometheus scrapes Kubernetes health metrics every 15 seconds.
Four alert rules are evaluated every 15 seconds.
Grafana dashboard shows cluster and workload health.
Grafana health API returned database: ok.
Dashboard validation showed 3 of 3 nodes ready, 25 of 25 healthy pods, and zero unhealthy pods.

Also fix the unfinished code block in `README.md`. At the end of the current file, add a closing triple backtick, then append:

```markdown
### Project 4: Kubernetes Monitoring, Grafana, and Alerting

Implemented a Git-managed monitoring stack for the Kubernetes health reporter:

- Prometheus metrics scraping and seven-day local retention
- Prometheus alert rules for reporter, node, and pod health
- Grafana deployment with a provisioned Prometheus datasource
- Kubernetes health dashboard provisioned automatically from ConfigMaps
- Secure Grafana admin password stored in a Kubernetes Secret, not Git
- Troubleshooting runbook for Calico CNI authentication failures

See [Day 8 documentation](docs/day-08-grafana-prometheus-alerting.md).