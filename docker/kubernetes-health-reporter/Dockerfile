FROM python:3.12-slim

ARG KUBECTL_VERSION=v1.30.14
ARG TARGETARCH=amd64

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && curl -fsSLO \
        "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" \
    && curl -fsSLO \
        "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl.sha256" \
    && echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check \
    && install -m 0755 kubectl /usr/local/bin/kubectl \
    && rm -f kubectl kubectl.sha256 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 reporter \
    && useradd \
        --uid 10001 \
        --gid 10001 \
        --create-home \
        reporter

WORKDIR /app

COPY --chown=reporter:reporter \
    python/automation/kubernetes_health_report.py \
    /app/kubernetes_health_report.py

RUN mkdir -p /app/output \
    && chown reporter:reporter /app/output

USER reporter

ENTRYPOINT ["python", "/app/kubernetes_health_report.py"]
