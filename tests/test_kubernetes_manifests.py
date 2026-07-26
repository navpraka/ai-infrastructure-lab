"""Policy tests for Kubernetes Health Reporter manifests."""

from pathlib import Path

import pytest
import yaml


MANIFEST_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "kubernetes"
    / "health-reporter"
)

MANIFEST_FILES = sorted(MANIFEST_DIRECTORY.glob("*.yaml"))


def load_manifest(filename: str) -> dict:
    """Load one Kubernetes manifest."""

    path = MANIFEST_DIRECTORY / filename

    with path.open(encoding="utf-8") as manifest_file:
        return yaml.safe_load(manifest_file)


@pytest.mark.parametrize("manifest_path", MANIFEST_FILES)
def test_manifest_has_required_metadata(
    manifest_path: Path,
) -> None:
    """Every manifest must contain basic Kubernetes metadata."""

    with manifest_path.open(encoding="utf-8") as manifest_file:
        manifest = yaml.safe_load(manifest_file)

    assert isinstance(manifest, dict)
    assert manifest.get("apiVersion")
    assert manifest.get("kind")
    assert manifest.get("metadata", {}).get("name")


def test_all_manifest_identities_are_unique() -> None:
    """Manifest kind, namespace, and name combinations must be unique."""

    identities = []

    for manifest_path in MANIFEST_FILES:
        with manifest_path.open(encoding="utf-8") as manifest_file:
            manifest = yaml.safe_load(manifest_file)

        metadata = manifest["metadata"]

        identities.append(
            (
                manifest["kind"],
                metadata.get("namespace", ""),
                metadata["name"],
            )
        )

    assert len(identities) == len(set(identities))


def test_cluster_role_is_read_only() -> None:
    """The reporter RBAC role must not grant write access."""

    cluster_role = load_manifest("05-cluster-role.yaml")
    allowed_verbs = {"get", "list"}

    for rule in cluster_role["rules"]:
        assert set(rule["verbs"]) <= allowed_verbs
        assert "*" not in rule.get("resources", [])
        assert "*" not in rule.get("nonResourceURLs", [])


def test_cronjob_uses_immutable_image() -> None:
    """The CronJob image must use an immutable SHA256 digest."""

    cronjob = load_manifest("07-cronjob.yaml")
    pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    image = pod_spec["containers"][0]["image"]

    assert "@sha256:" in image
    assert not image.endswith(":latest")


def test_cronjob_runs_as_non_root() -> None:
    """The CronJob must enforce non-root execution."""

    cronjob = load_manifest("07-cronjob.yaml")
    pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    pod_security = pod_spec["securityContext"]
    container_security = pod_spec["containers"][0]["securityContext"]

    assert pod_security["runAsNonRoot"] is True
    assert pod_security["runAsUser"] == 10001
    assert pod_security["runAsGroup"] == 10001
    assert container_security["allowPrivilegeEscalation"] is False
    assert container_security["readOnlyRootFilesystem"] is True
    assert container_security["capabilities"]["drop"] == ["ALL"]


def test_persistent_volume_retains_reports() -> None:
    """The report PV must retain data after claim deletion."""

    persistent_volume = load_manifest(
        "02-persistent-volume.yaml"
    )

    assert (
        persistent_volume["spec"]["persistentVolumeReclaimPolicy"]
        == "Retain"
    )


def test_cronjob_forbids_concurrent_runs() -> None:
    """Scheduled reporter runs must not overlap."""

    cronjob = load_manifest("07-cronjob.yaml")

    assert cronjob["spec"]["concurrencyPolicy"] == "Forbid"
    assert cronjob["spec"]["schedule"] == "*/15 * * * *"
