"""Policy tests for the Prometheus monitoring manifests."""

from pathlib import Path

import pytest
import yaml
import json


MANIFEST_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "kubernetes"
    / "monitoring"
)

MANIFEST_FILES = sorted(MANIFEST_DIRECTORY.glob("*.yaml"))


def load_manifest(filename: str) -> dict:
    """Load one monitoring manifest."""

    path = MANIFEST_DIRECTORY / filename

    with path.open(encoding="utf-8") as manifest_file:
        return yaml.safe_load(manifest_file)


@pytest.mark.parametrize("manifest_path", MANIFEST_FILES)
def test_monitoring_manifest_has_required_metadata(
    manifest_path: Path,
) -> None:
    """Every monitoring manifest must have basic metadata."""

    with manifest_path.open(encoding="utf-8") as manifest_file:
        manifest = yaml.safe_load(manifest_file)

    assert isinstance(manifest, dict)
    assert manifest.get("apiVersion")
    assert manifest.get("kind")
    assert manifest.get("metadata", {}).get("name")


def test_monitoring_namespace_enforces_restricted_security() -> None:
    """The monitoring namespace must enforce restricted Pod Security."""

    namespace = load_manifest("00-namespace.yaml")
    labels = namespace["metadata"]["labels"]

    assert (
        labels["pod-security.kubernetes.io/enforce"]
        == "restricted"
    )
    assert (
        labels["pod-security.kubernetes.io/audit"]
        == "restricted"
    )
    assert (
        labels["pod-security.kubernetes.io/warn"]
        == "restricted"
    )


def test_prometheus_scrapes_health_reporter_metrics() -> None:
    """Prometheus must scrape the health reporter endpoint."""

    config_map = load_manifest("01-prometheus-config.yaml")
    prometheus_config = yaml.safe_load(
        config_map["data"]["prometheus.yml"]
    )

    jobs = {
        job["job_name"]: job
        for job in prometheus_config["scrape_configs"]
    }

    reporter_job = jobs["kubernetes-health-reporter"]

    assert (
        reporter_job["metrics_path"]
        == "/kubernetes-health-report.prom"
    )
    assert (
        reporter_job["fallback_scrape_protocol"]
        == "PrometheusText0.0.4"
    )

    targets = reporter_job["static_configs"][0]["targets"]

    assert (
        "health-reporter-metrics."
        "ai-infrastructure.svc.cluster.local:8080"
        in targets
    )


def test_prometheus_persistent_volume_is_retained() -> None:
    """Prometheus data must use retained local persistent storage."""

    persistent_volume = load_manifest(
        "02-prometheus-persistent-volume.yaml"
    )

    spec = persistent_volume["spec"]

    assert spec["persistentVolumeReclaimPolicy"] == "Retain"
    assert spec["storageClassName"] == "local-storage"
    assert spec["capacity"]["storage"] == "2Gi"
    assert (
        spec["local"]["path"]
        == "/var/lib/ai-infrastructure-lab/prometheus"
    )

    expressions = (
        spec["nodeAffinity"]["required"]
        ["nodeSelectorTerms"][0]["matchExpressions"]
    )

    assert expressions[0]["values"] == ["k8s-worker02"]


def test_prometheus_claim_matches_persistent_volume() -> None:
    """The Prometheus claim must request the expected storage."""

    claim = load_manifest(
        "03-prometheus-persistent-volume-claim.yaml"
    )

    spec = claim["spec"]

    assert spec["storageClassName"] == "local-storage"
    assert spec["accessModes"] == ["ReadWriteOnce"]
    assert spec["resources"]["requests"]["storage"] == "2Gi"


def test_prometheus_deployment_is_hardened() -> None:
    """Prometheus must run with hardened container security."""

    deployment = load_manifest("04-prometheus-deployment.yaml")
    pod_spec = deployment["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]
    security = container["securityContext"]

    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert pod_spec["securityContext"]["runAsUser"] == 65534
    assert (
        pod_spec["securityContext"]["seccompProfile"]["type"]
        == "RuntimeDefault"
    )

    assert security["allowPrivilegeEscalation"] is False
    assert security["readOnlyRootFilesystem"] is True
    assert security["capabilities"]["drop"] == ["ALL"]

    image = container["image"]

    assert "@sha256:" in image
    assert not image.endswith(":latest")


def test_prometheus_has_resource_and_retention_controls() -> None:
    """Prometheus must have bounded resource and data usage."""

    deployment = load_manifest("04-prometheus-deployment.yaml")
    container = (
        deployment["spec"]["template"]["spec"]["containers"][0]
    )

    assert container["resources"]["requests"]["cpu"] == "100m"
    assert container["resources"]["requests"]["memory"] == "256Mi"
    assert container["resources"]["limits"]["cpu"] == "500m"
    assert container["resources"]["limits"]["memory"] == "512Mi"

    arguments = container["args"]

    assert "--storage.tsdb.retention.time=7d" in arguments
    assert "--storage.tsdb.retention.size=1GB" in arguments
    assert container["readinessProbe"]["httpGet"]["path"] == "/-/ready"
    assert container["livenessProbe"]["httpGet"]["path"] == "/-/healthy"


def test_prometheus_service_is_internal() -> None:
    """Prometheus must only be exposed inside the cluster."""

    service = load_manifest("05-prometheus-service.yaml")
    spec = service["spec"]
    port = spec["ports"][0]

    assert spec["type"] == "ClusterIP"
    assert port["port"] == 9090
    assert port["targetPort"] == "http"


def test_prometheus_loads_health_reporter_alert_rules() -> None:
    """Prometheus must load the Kubernetes health alert rules."""

    config_map = load_manifest("01-prometheus-config.yaml")
    prometheus_config = yaml.safe_load(
        config_map["data"]["prometheus.yml"]
    )

    assert prometheus_config["rule_files"] == [
        "/etc/prometheus/rules/*.yaml"
    ]

    rules_config_map = load_manifest(
        "06-prometheus-alert-rules.yaml"
    )
    rules_document = yaml.safe_load(
        rules_config_map["data"]["health-reporter-alerts.yaml"]
    )

    rules = rules_document["groups"][0]["rules"]
    alert_names = {rule["alert"] for rule in rules}

    assert alert_names == {
        "KubernetesHealthReporterTargetDown",
        "KubernetesHealthReporterJobFailed",
        "KubernetesNodesNotReady",
        "KubernetesUnhealthyPodsDetected",
    }


def test_grafana_provisions_prometheus_and_dashboard() -> None:
    """Grafana must provision the internal Prometheus datasource."""

    provisioning = load_manifest("07-grafana-provisioning.yaml")
    datasource_config = yaml.safe_load(
        provisioning["data"]["datasources.yaml"]
    )
    datasource = datasource_config["datasources"][0]

    assert datasource["name"] == "Prometheus"
    assert datasource["uid"] == "prometheus"
    assert (
        datasource["url"]
        == "http://prometheus.monitoring.svc.cluster.local:9090"
    )
    assert datasource["isDefault"] is True
    assert datasource["editable"] is False

    dashboard_config_map = load_manifest(
        "08-grafana-dashboard.yaml"
    )
    dashboard = json.loads(
        dashboard_config_map[
            "data"
        ]["kubernetes-health-dashboard.json"]
    )

    assert dashboard["title"] == "Kubernetes Health Reporter"
    assert dashboard["uid"] == "kubernetes-health-reporter"

    panel_titles = {panel["title"] for panel in dashboard["panels"]}

    assert panel_titles == {
        "Unhealthy Pods",
        "Nodes Ready / Total",
        "Healthy Pods / Total",
        "Warning Events",
        "Node Health Trend",
        "Pod Health Trend",
    }


def test_grafana_deployment_uses_secret_and_hardening() -> None:
    """Grafana must use a Secret and restricted security settings."""

    deployment = load_manifest("09-grafana-deployment.yaml")
    pod_spec = deployment["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]
    security = container["securityContext"]

    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert pod_spec["securityContext"]["runAsUser"] == 472
    assert (
        pod_spec["securityContext"]["seccompProfile"]["type"]
        == "RuntimeDefault"
    )

    assert container["image"] == "grafana/grafana:11.5.2"
    assert security["allowPrivilegeEscalation"] is False
    assert security["capabilities"]["drop"] == ["ALL"]

    environment = {
        item["name"]: item
        for item in container["env"]
    }

    password_reference = environment[
        "GF_SECURITY_ADMIN_PASSWORD"
    ]["valueFrom"]["secretKeyRef"]

    assert password_reference["name"] == "grafana-admin-credentials"
    assert password_reference["key"] == "admin-password"


def test_grafana_service_is_internal() -> None:
    """Grafana must only be exposed inside the cluster."""

    service = load_manifest("10-grafana-service.yaml")
    spec = service["spec"]
    port = spec["ports"][0]

    assert spec["type"] == "ClusterIP"
    assert port["port"] == 3000
    assert port["targetPort"] == "http"