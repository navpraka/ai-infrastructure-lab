# Day 3 — Calico Typha and BIRD RCA

Date: 26 July 2026

## Environment

- Kubernetes: v1.30.14
- Operating system: Ubuntu 22.04.5 LTS
- Networking: Calico v3.28.0
- Control plane: k8s-master
- Workers: k8s-worker01 and k8s-worker02

## Incident Summary

The Calico node pod on `k8s-worker01` remained Running but not Ready:

```text
calico-node-2zmdq   0/1   Running

BIRD is not ready
Unable to connect to /var/run/calico/bird.ctl
Connection refused

Impact

The Kubernetes node remained Ready, but its Calico networking component was
not healthy. This could affect pod networking, route programming and workload
scheduling on k8s-worker01.

Investigation

Typha pods were healthy on:

k8s-master: 192.168.48.129
k8s-worker02: 192.168.48.134

The Typha service exposed TCP port 5473.

Layer-3 connectivity from worker01 was successful:

Ping to 192.168.48.129: successful
Ping to 192.168.48.134: successful

TCP connectivity failed:

192.168.48.129:5473: timed out
192.168.48.134:5473: timed out

Calico logs showed that calico-confd could not connect to either Typha
endpoint. Consequently, it could not generate bird.cfg, BIRD could not start,
and the bird.ctl socket was unavailable.

Root Cause

UFW was active with a default inbound deny policy. TCP port 5473, required for
Calico node-to-Typha communication, was not allowed on the Typha destination
nodes.

Worker01 was affected because it did not have a local Typha pod and therefore
needed remote access to Typha on the other nodes.

Resolution

TCP port 5473 was allowed only from the Kubernetes node subnet:

sudo ufw allow from 192.168.48.0/24 \
  to any port 5473 proto tcp

The rule was applied to the Kubernetes nodes so that Typha rescheduling would
not recreate the problem.

No Calico pod restart was required. Calico automatically retried the
connection and recovered.

Validation

After the firewall correction:

calico-node-2zmdq   1/1   Running
Number of nodes with BGP peering established = 2

The Health Reporter v2 result was:

Overall status  : HEALTHY
Ready nodes     : 3/3
Healthy pods    : 21/21
Unhealthy pods  : 0
CI/CD exit code : 0
Preventive Actions
Maintain a Kubernetes and Calico firewall-port matrix.
Permit Typha TCP 5473 only from trusted cluster-node networks.
Validate required ports whenever UFW or another host firewall is enabled.
Monitor Calico readiness, restart counts and warning events.
Use the automated Kubernetes Health Reporter for regular health checks.
