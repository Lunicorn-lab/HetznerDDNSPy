# syntax=docker/dockerfile:1.7
# ---- builder ---------------------------------------------------------------
FROM python:3.12-slim-bookworm@sha256:5c73034c2bc151596ee0f1335610735162ee2b148816710706afec4757ad5b1e AS builder

ARG PYTHONDONTWRITEBYTECODE=1
ARG PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=$PYTHONDONTWRITEBYTECODE \
    PYTHONUNBUFFERED=$PYTHONUNBUFFERED \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install .

# ---- runtime ---------------------------------------------------------------
# Distroless nonroot: no shell, no package manager, UID/GID 65532.
FROM gcr.io/distroless/python3-debian12:nonroot@sha256:7d1042ce588ab97019fe95c24ffca7bc5a82ccdac572511d5e09bda4435c89c5

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=2.0.0

LABEL org.opencontainers.image.title="hetzner-ddns" \
      org.opencontainers.image.description="Minimal DynDNS updater for Hetzner DNS API" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/Lunicorn/HetznerDDNSPy" \
      org.opencontainers.image.licenses="GPL-3.0-or-later" \
      org.opencontainers.image.base.name="gcr.io/distroless/python3-debian12:nonroot"

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STATE_DIR=/var/lib/hetzner_ddns \
    LOG_FORMAT=json

# Distroless "nonroot" image already uses uid 65532.
USER 65532:65532
WORKDIR /app

VOLUME ["/var/lib/hetzner_ddns"]

ENTRYPOINT ["/opt/venv/bin/hetzner-ddns"]
CMD ["--once"]
