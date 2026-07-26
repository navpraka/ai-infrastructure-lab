"""Generate an actionable Kubernetes cluster health report."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


OUTPUT_DIRECTORY = Path("output")
JSON_REPORT = OUTPUT_DIRECTORY / "kubernetes-health-report.json"
TEXT_REPORT = OUTPUT_DIRECTORY / "kubernetes-health-report.txt"

PROMETHEUS_REPORT = (
    OUTPUT_DIRECTORY / "kubernetes-health-report.prom"
)

EXIT_CODES = {
    "HEALTHY": 0,
    "WARNING": 1,
    "CRITICAL": 2,
}

CRITICAL_POD_REASONS = {
    "CrashLoopBackOff",
    "CreateContainerConfigError",
    "CreateContainerError",
    "ErrImagePull",
    "ImagePullBackOff",
    "InvalidImageName",
    "OOMKilled",
    "RunContainerError",
}


def run_command(command: list[str]) -> str:
    """Run a command and return its standard output."""

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return result.stdout.strip()
    except FileNotFoundError as error:
        raise RuntimeError(
            f"Required command is not installed: {command[0]}"
        ) from error
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() or error.stdout.strip()
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\n{message}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"Command timed out: {' '.join(command)}"
        ) from error


def run_kubectl_json(arguments: list[str]) -> dict[str, Any]:
    """Run kubectl and parse its JSON output."""

    output = run_command(["kubectl", *arguments, "-o", "json"])
    return json.loads(output)


def collect_nodes() -> list[dict[str, Any]]:
    """Collect Kubernetes node health information."""

    data = run_kubectl_json(["get", "nodes"])
    nodes: list[dict[str, Any]] = []

    for item in data.get("items", []):
        metadata = item.get("metadata", {})
        status = item.get("status", {})
        conditions = status.get("conditions", [])
        addresses = status.get("addresses", [])

        ready_condition = next(
            (
                condition
                for condition in conditions
                if condition.get("type") == "Ready"
            ),
            {},
        )
        internal_ip = next(
            (
                address.get("address", "Unknown")
                for address in addresses
                if address.get("type") == "InternalIP"
            ),
            "Unknown",
        )

        nodes.append(
            {
                "name": metadata.get("name", "Unknown"),
                "ready": ready_condition.get("status") == "True",
                "status": ready_condition.get("status", "Unknown"),
                "reason": ready_condition.get("reason", "Unknown"),
                "message": ready_condition.get("message", ""),
                "internal_ip": internal_ip,
                "kubelet_version": (
                    status.get("nodeInfo", {})
                    .get("kubeletVersion", "Unknown")
                ),
            }
        )

    return nodes


def get_problem_details(
    item: dict[str, Any],
) -> tuple[str, str]:
    """Return the most useful reason and message for an unhealthy pod."""

    status = item.get("status", {})
    all_statuses = [
        *status.get("initContainerStatuses", []),
        *status.get("containerStatuses", []),
    ]

    for container in all_statuses:
        state = container.get("state", {})
        waiting = state.get("waiting")

        if waiting:
            return (
                waiting.get("reason", "ContainerWaiting"),
                waiting.get("message", ""),
            )

    for container in all_statuses:
        terminated = container.get("state", {}).get("terminated")

        if terminated and terminated.get("exitCode", 0) != 0:
            return (
                terminated.get("reason", "ContainerTerminated"),
                terminated.get("message", ""),
            )

    phase = status.get("phase", "Unknown")
    reason = status.get("reason")
    message = status.get("message", "")

    if reason:
        return reason, message
    if phase == "Pending":
        return "Pending", message
    if phase == "Failed":
        return "Failed", message
    if phase == "Unknown":
        return "Unknown", message

    return "ContainersNotReady", message


def recommend_action(reason: str) -> str:
    """Return a practical first troubleshooting action."""

    if reason in {"ErrImagePull", "ImagePullBackOff", "InvalidImageName"}:
        return (
            "Verify the image name, registry access and imagePullSecrets."
        )
    if reason == "CrashLoopBackOff":
        return (
            "Check current and previous container logs, then inspect the "
            "pod events."
        )
    if reason == "OOMKilled":
        return (
            "Review memory usage, limits and requests; inspect previous logs."
        )
    if reason == "Pending":
        return (
            "Describe the pod and check scheduling, resources, taints and PVCs."
        )
    if reason in {
        "CreateContainerConfigError",
        "CreateContainerError",
        "RunContainerError",
    }:
        return (
            "Describe the pod and verify referenced Secrets, ConfigMaps, "
            "volumes and security settings."
        )
    if reason == "ContainersNotReady":
        return (
            "Describe the pod and inspect readiness probes and container logs."
        )
    if reason in {"Failed", "Unknown"}:
        return "Describe the pod and inspect its events and container logs."

    return "Describe the pod and inspect its events and container logs."


def collect_pods() -> dict[str, Any]:
    """Collect cluster-wide pod health and troubleshooting information."""

    data = run_kubectl_json(["get", "pods", "--all-namespaces"])

    total = 0
    healthy = 0
    unhealthy: list[dict[str, Any]] = []

    for item in data.get("items", []):
        total += 1

        metadata = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})
        phase = status.get("phase", "Unknown")
        container_statuses = status.get("containerStatuses", [])

        ready_count = sum(
            1
            for container in container_statuses
            if container.get("ready", False)
        )
        container_count = len(container_statuses)
        all_ready = bool(container_statuses) and (
            ready_count == container_count
        )

        if phase == "Succeeded" or (
            phase == "Running" and all_ready
        ):
            healthy += 1
            continue

        reason, message = get_problem_details(item)
        severity = (
            "CRITICAL"
            if reason in CRITICAL_POD_REASONS
            or phase in {"Failed", "Unknown"}
            else "WARNING"
        )
        restart_count = sum(
            container.get("restartCount", 0)
            for container in container_statuses
        )

        unhealthy.append(
            {
                "namespace": metadata.get("namespace", "default"),
                "name": metadata.get("name", "Unknown"),
                "node": spec.get("nodeName", "Unscheduled"),
                "phase": phase,
                "ready": f"{ready_count}/{container_count}",
                "restarts": restart_count,
                "reason": reason,
                "message": message,
                "severity": severity,
                "recommendation": recommend_action(reason),
            }
        )

    return {
        "total": total,
        "healthy": healthy,
        "unhealthy_count": len(unhealthy),
        "unhealthy": unhealthy,
    }


def collect_namespaces() -> list[str]:
    """Collect namespace names."""

    data = run_kubectl_json(["get", "namespaces"])
    return sorted(
        item["metadata"]["name"]
        for item in data.get("items", [])
    )


def event_timestamp(item: dict[str, Any]) -> str:
    """Return the best available event timestamp."""

    return (
        item.get("eventTime")
        or item.get("series", {}).get("lastObservedTime")
        or item.get("lastTimestamp")
        or item.get("metadata", {}).get("creationTimestamp")
        or ""
    )


def collect_warning_events() -> list[dict[str, Any]]:
    """Collect and sort recent warning events from all namespaces."""

    data = run_kubectl_json(
        [
            "get",
            "events",
            "--all-namespaces",
            "--field-selector",
            "type=Warning",
        ]
    )

    items = sorted(
        data.get("items", []),
        key=event_timestamp,
        reverse=True,
    )[:20]

    events: list[dict[str, Any]] = []

    for item in items:
        metadata = item.get("metadata", {})
        involved_object = item.get("involvedObject", {})

        events.append(
            {
                "namespace": metadata.get("namespace", "default"),
                "reason": item.get("reason", "Unknown"),
                "object": (
                    f"{involved_object.get('kind', 'Object')}/"
                    f"{involved_object.get('name', 'Unknown')}"
                ),
                "count": item.get("count", 1),
                "last_seen": event_timestamp(item) or "Unknown",
                "message": item.get("message", ""),
            }
        )

    return events


def determine_health(
    nodes: list[dict[str, Any]],
    pods: dict[str, Any],
) -> tuple[str, list[str]]:
    """Determine current health from node and pod state."""

    findings: list[str] = []
    not_ready_nodes = [
        node["name"]
        for node in nodes
        if not node["ready"]
    ]
    critical_pods = [
        f"{pod['namespace']}/{pod['name']}"
        for pod in pods["unhealthy"]
        if pod["severity"] == "CRITICAL"
    ]

    if not_ready_nodes:
        findings.append(
            "NotReady nodes: " + ", ".join(not_ready_nodes)
        )
    if critical_pods:
        findings.append(
            "Critical pods: " + ", ".join(critical_pods)
        )

    if not_ready_nodes or critical_pods:
        return "CRITICAL", findings

    if pods["unhealthy_count"]:
        findings.append(
            f"{pods['unhealthy_count']} pod(s) are not currently healthy."
        )
        return "WARNING", findings

    findings.append("All nodes and current pods are healthy.")
    return "HEALTHY", findings


def build_text_report(report: dict[str, Any]) -> str:
    """Convert the structured report into readable text."""

    ready_nodes = sum(
        1
        for node in report["nodes"]
        if node["ready"]
    )

    lines = [
        "=" * 72,
        "Kubernetes Cluster Health Report v2",
        "=" * 72,
        f"Overall status     : {report['overall_status']}",
        f"CI/CD exit code    : {report['exit_code']}",
        f"Generated at       : {report['generated_at']}",
        f"Cluster version    : {report['cluster_version']}",
        f"Ready nodes        : {ready_nodes}/{len(report['nodes'])}",
        f"Healthy pods       : "
        f"{report['pods']['healthy']}/{report['pods']['total']}",
        f"Unhealthy pods     : {report['pods']['unhealthy_count']}",
        f"Namespace count    : {len(report['namespaces'])}",
        "",
        "Current Findings:",
    ]

    for finding in report["findings"]:
        lines.append(f"- {finding}")

    lines.extend(["", "Nodes:"])

    for node in report["nodes"]:
        lines.append(
            f"- {node['name']}: "
            f"{'Ready' if node['ready'] else 'NotReady'} "
            f"ip={node['internal_ip']} "
            f"version={node['kubelet_version']}"
        )

    lines.extend(["", "Unhealthy Pods:"])

    if report["pods"]["unhealthy"]:
        for pod in report["pods"]["unhealthy"]:
            lines.extend(
                [
                    (
                        f"- [{pod['severity']}] "
                        f"{pod['namespace']}/{pod['name']} "
                        f"node={pod['node']} phase={pod['phase']} "
                        f"ready={pod['ready']} "
                        f"restarts={pod['restarts']}"
                    ),
                    f"  Reason: {pod['reason']}",
                    f"  Action: {pod['recommendation']}",
                ]
            )
            if pod["message"]:
                lines.append(f"  Message: {pod['message']}")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "Recent Warning Events (historical context only):",
        ]
    )

    if report["warning_events"]:
        for event in report["warning_events"]:
            lines.append(
                f"- [{event['namespace']}] {event['reason']} "
                f"object={event['object']} count={event['count']} "
                f"last_seen={event['last_seen']}: "
                f"{event['message']}"
            )
    else:
        lines.append("- None")

    lines.append("=" * 72)
    return "\n".join(lines)

def build_prometheus_metrics(report: dict[str, Any]) -> str:
    """Convert the report into Prometheus text exposition format."""

    status = report["overall_status"].lower()
    generated_timestamp = datetime.fromisoformat(
        report["generated_at"]
    ).timestamp()

    lines = [
        "# HELP kubernetes_health_reporter_last_run_status "
        "Health status from the latest reporter execution.",
        "# TYPE kubernetes_health_reporter_last_run_status gauge",
    ]

    for possible_status in ("healthy", "warning", "critical"):
        value = 1 if status == possible_status else 0
        lines.append(
            "kubernetes_health_reporter_last_run_status"
            f'{{status="{possible_status}"}} {value}'
        )

    lines.extend(
        [
            "# HELP kubernetes_health_reporter_exit_code "
            "Exit code from the latest reporter execution.",
            "# TYPE kubernetes_health_reporter_exit_code gauge",
            "kubernetes_health_reporter_exit_code "
            f"{report['exit_code']}",
            "# HELP kubernetes_health_reporter_last_run_timestamp_seconds "
            "Unix timestamp of the latest reporter execution.",
            "# TYPE "
            "kubernetes_health_reporter_last_run_timestamp_seconds "
            "gauge",
            "kubernetes_health_reporter_last_run_timestamp_seconds "
            f"{generated_timestamp:.0f}",
            "# HELP kubernetes_health_reporter_nodes_total "
            "Total Kubernetes nodes.",
            "# TYPE kubernetes_health_reporter_nodes_total gauge",
            "kubernetes_health_reporter_nodes_total "
            f"{len(report['nodes'])}",
            "# HELP kubernetes_health_reporter_nodes_ready "
            "Ready Kubernetes nodes.",
            "# TYPE kubernetes_health_reporter_nodes_ready gauge",
            "kubernetes_health_reporter_nodes_ready "
            f"{sum(node['ready'] for node in report['nodes'])}",
            "# HELP kubernetes_health_reporter_pods_total "
            "Total Kubernetes pods.",
            "# TYPE kubernetes_health_reporter_pods_total gauge",
            "kubernetes_health_reporter_pods_total "
            f"{report['pods']['total']}",
            "# HELP kubernetes_health_reporter_pods_healthy "
            "Healthy Kubernetes pods.",
            "# TYPE kubernetes_health_reporter_pods_healthy gauge",
            "kubernetes_health_reporter_pods_healthy "
            f"{report['pods']['healthy']}",
            "# HELP kubernetes_health_reporter_pods_unhealthy "
            "Unhealthy Kubernetes pods.",
            "# TYPE kubernetes_health_reporter_pods_unhealthy gauge",
            "kubernetes_health_reporter_pods_unhealthy "
            f"{report['pods']['unhealthy_count']}",
            "# HELP kubernetes_health_reporter_namespaces_total "
            "Total Kubernetes namespaces.",
            "# TYPE kubernetes_health_reporter_namespaces_total gauge",
            "kubernetes_health_reporter_namespaces_total "
            f"{len(report['namespaces'])}",
            "# HELP kubernetes_health_reporter_warning_events_total "
            "Warning events included in the latest report.",
            "# TYPE kubernetes_health_reporter_warning_events_total "
            "gauge",
            "kubernetes_health_reporter_warning_events_total "
            f"{len(report['warning_events'])}",
        ]
    )

    return "\n".join(lines) + "\n"

def main() -> int:
    """Collect health data and write JSON and text reports."""

    if shutil.which("kubectl") is None:
        print("ERROR: kubectl is not installed or not in PATH.")
        return EXIT_CODES["CRITICAL"]

    try:
        OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

        version_data = run_kubectl_json(["version"])
        cluster_version = (
            version_data.get("serverVersion", {})
            .get("gitVersion", "Unknown")
        )
        nodes = collect_nodes()
        pods = collect_pods()
        overall_status, findings = determine_health(nodes, pods)

        report = {
            "report_version": 2,
            "generated_at": datetime.now().astimezone().isoformat(),
            "overall_status": overall_status,
            "exit_code": EXIT_CODES[overall_status],
            "findings": findings,
            "cluster_version": cluster_version,
            "nodes": nodes,
            "pods": pods,
            "namespaces": collect_namespaces(),
            "warning_events": collect_warning_events(),
        }

        JSON_REPORT.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        text_report = build_text_report(report)
        TEXT_REPORT.write_text(text_report, encoding="utf-8")
        prometheus_metrics = build_prometheus_metrics(report)
        PROMETHEUS_REPORT.write_text(
            prometheus_metrics,
            encoding="utf-8",
        )

        print(text_report)
        print()
        print(f"JSON report written to: {JSON_REPORT}")
        print(f"Text report written to: {TEXT_REPORT}")
        print(
            "Prometheus report written to: "
            f"{PROMETHEUS_REPORT}"
        )
        return EXIT_CODES[overall_status]

    except (RuntimeError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}")
        return EXIT_CODES["CRITICAL"]


if __name__ == "__main__":
    sys.exit(main())
