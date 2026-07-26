"""Unit tests for the Kubernetes Health Reporter."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


AUTOMATION_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "python"
    / "automation"
)

sys.path.insert(0, str(AUTOMATION_DIRECTORY))

import kubernetes_health_report as reporter  # noqa: E402


def ready_nodes() -> list[dict[str, object]]:
    """Return a basic healthy node fixture."""

    return [
        {
            "name": "k8s-master",
            "ready": True,
        },
        {
            "name": "k8s-worker01",
            "ready": True,
        },
    ]


def test_determine_health_returns_healthy() -> None:
    """All ready nodes and healthy pods must return HEALTHY."""

    pods = {
        "unhealthy_count": 0,
        "unhealthy": [],
    }

    status, findings = reporter.determine_health(
        ready_nodes(),
        pods,
    )

    assert status == "HEALTHY"
    assert findings == [
        "All nodes and current pods are healthy."
    ]


def test_determine_health_returns_warning() -> None:
    """A non-critical unhealthy pod must return WARNING."""

    pods = {
        "unhealthy_count": 1,
        "unhealthy": [
            {
                "namespace": "default",
                "name": "pending-pod",
                "severity": "WARNING",
            }
        ],
    }

    status, findings = reporter.determine_health(
        ready_nodes(),
        pods,
    )

    assert status == "WARNING"
    assert "1 pod(s)" in findings[0]


def test_determine_health_returns_critical_for_pod() -> None:
    """A critical pod must return CRITICAL."""

    pods = {
        "unhealthy_count": 1,
        "unhealthy": [
            {
                "namespace": "default",
                "name": "crashing-pod",
                "severity": "CRITICAL",
            }
        ],
    }

    status, findings = reporter.determine_health(
        ready_nodes(),
        pods,
    )

    assert status == "CRITICAL"
    assert "default/crashing-pod" in findings[0]


def test_determine_health_returns_critical_for_node() -> None:
    """A NotReady node must return CRITICAL."""

    nodes = ready_nodes()
    nodes[1]["ready"] = False

    pods = {
        "unhealthy_count": 0,
        "unhealthy": [],
    }

    status, findings = reporter.determine_health(
        nodes,
        pods,
    )

    assert status == "CRITICAL"
    assert "k8s-worker01" in findings[0]


@pytest.mark.parametrize(
    ("reason", "expected_text"),
    [
        ("CrashLoopBackOff", "previous container logs"),
        ("ImagePullBackOff", "registry access"),
        ("OOMKilled", "memory usage"),
        ("Pending", "scheduling"),
        ("ContainersNotReady", "readiness probes"),
    ],
)
def test_recommend_action(
    reason: str,
    expected_text: str,
) -> None:
    """Each common failure should provide useful guidance."""

    recommendation = reporter.recommend_action(reason)

    assert expected_text in recommendation


def test_get_problem_details_for_waiting_container() -> None:
    """The reporter must extract a container waiting reason."""

    pod = {
        "status": {
            "phase": "Pending",
            "containerStatuses": [
                {
                    "state": {
                        "waiting": {
                            "reason": "ImagePullBackOff",
                            "message": "Unable to pull image",
                        }
                    }
                }
            ],
        }
    }

    reason, message = reporter.get_problem_details(pod)

    assert reason == "ImagePullBackOff"
    assert message == "Unable to pull image"


def test_event_timestamp_uses_last_timestamp() -> None:
    """The event parser must use the available event timestamp."""

    event = {
        "lastTimestamp": "2026-07-26T10:00:50Z",
        "metadata": {
            "creationTimestamp": "2026-07-26T09:00:00Z"
        },
    }

    assert (
        reporter.event_timestamp(event)
        == "2026-07-26T10:00:50Z"
    )
