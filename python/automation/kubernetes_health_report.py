"""Generate a basic Kubernetes cluster health report."""

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
        conditions = item.get("status", {}).get("conditions", [])

        ready_condition = next(
            (
                condition
                for condition in conditions
                if condition.get("type") == "Ready"
            ),
            {},
        )

        nodes.append(
            {
                "name": item["metadata"]["name"],
                "ready": ready_condition.get("status") == "True",
                "status": ready_condition.get("status", "Unknown"),
                "reason": ready_condition.get("reason", "Unknown"),
                "kubelet_version": (
                    item.get("status", {})
                    .get("nodeInfo", {})
                    .get("kubeletVersion", "Unknown")
                ),
            }
        )

    return nodes


def collect_pods() -> dict[str, Any]:
    """Collect cluster-wide pod health information."""

    data = run_kubectl_json(["get", "pods", "--all-namespaces"])

    total = 0
    healthy = 0
    unhealthy: list[dict[str, str]] = []

    for item in data.get("items", []):
        total += 1

        metadata = item.get("metadata", {})
        status = item.get("status", {})
        phase = status.get("phase", "Unknown")

        container_statuses = status.get("containerStatuses", [])
        all_ready = bool(container_statuses) and all(
            container.get("ready", False)
            for container in container_statuses
        )

        if phase == "Succeeded" or (
            phase == "Running" and all_ready
        ):
            healthy += 1
        else:
            unhealthy.append(
                {
                    "namespace": metadata.get(
                        "namespace",
                        "default",
                    ),
                    "name": metadata.get("name", "Unknown"),
                    "phase": phase,
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


def collect_warning_events() -> list[dict[str, str]]:
    """Collect recent warning events from all namespaces."""

    data = run_kubectl_json(
        [
            "get",
            "events",
            "--all-namespaces",
            "--field-selector",
            "type=Warning",
        ]
    )

    events: list[dict[str, str]] = []

    for item in data.get("items", [])[-20:]:
        metadata = item.get("metadata", {})

        events.append(
            {
                "namespace": metadata.get(
                    "namespace",
                    "default",
                ),
                "reason": item.get("reason", "Unknown"),
                "message": item.get("message", ""),
            }
        )

    return events


def build_text_report(report: dict[str, Any]) -> str:
    """Convert the structured report into readable text."""

    lines = [
        "=" * 72,
        "Kubernetes Cluster Health Report",
        "=" * 72,
        f"Generated at       : {report['generated_at']}",
        f"Cluster version    : {report['cluster_version']}",
        f"Node count         : {len(report['nodes'])}",
        f"Pod count          : {report['pods']['total']}",
        f"Healthy pods       : {report['pods']['healthy']}",
        f"Unhealthy pods     : "
        f"{report['pods']['unhealthy_count']}",
        f"Namespace count    : {len(report['namespaces'])}",
        "",
        "Nodes:",
    ]

    for node in report["nodes"]:
        lines.append(
            f"- {node['name']}: "
            f"{'Ready' if node['ready'] else 'NotReady'} "
            f"({node['kubelet_version']})"
        )

    lines.append("")
    lines.append("Unhealthy Pods:")

    if report["pods"]["unhealthy"]:
        for pod in report["pods"]["unhealthy"]:
            lines.append(
                f"- {pod['namespace']}/{pod['name']} "
                f"phase={pod['phase']}"
            )
    else:
        lines.append("- None")

    lines.append("")
    lines.append("Recent Warning Events:")

    if report["warning_events"]:
        for event in report["warning_events"]:
            lines.append(
                f"- [{event['namespace']}] "
                f"{event['reason']}: {event['message']}"
            )
    else:
        lines.append("- None")

    lines.append("=" * 72)
    return "\n".join(lines)


def main() -> int:
    """Collect health data and write JSON and text reports."""

    if shutil.which("kubectl") is None:
        print("ERROR: kubectl is not installed or not in PATH.")
        return 1

    try:
        OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

        version_data = run_kubectl_json(["version"])
        cluster_version = (
            version_data.get("serverVersion", {})
            .get("gitVersion", "Unknown")
        )

        report = {
            "generated_at": datetime.now().astimezone().isoformat(),
            "cluster_version": cluster_version,
            "nodes": collect_nodes(),
            "pods": collect_pods(),
            "namespaces": collect_namespaces(),
            "warning_events": collect_warning_events(),
        }

        JSON_REPORT.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        text_report = build_text_report(report)
        TEXT_REPORT.write_text(
            text_report,
            encoding="utf-8",
        )

        print(text_report)
        print()
        print(f"JSON report written to: {JSON_REPORT}")
        print(f"Text report written to: {TEXT_REPORT}")
        return 0

    except RuntimeError as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())