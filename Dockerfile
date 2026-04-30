# Pin to minor (0.2) instead of patch (0.2.x). The agent-core fan-out
# workflow rebuilds this image whenever a v* tag is published, so we'll
# pick up patch releases on the next rebuild without anyone editing this
# file. Bump explicitly to 0.3 / 1.0 / etc. when a minor or major lands
# (those are the changes likely to break the contract).
FROM ghcr.io/knoxville-ai/agent-core:0.2

# Install SME-specific Python deps on top of the agent-core base image.
# Listed explicitly (not via `pip install .`) so we don't disturb the
# base image's pinned agent-core / requests versions.
#   - pypdf:    sanmar_parse_po_pdf (PDF text extraction)
#   - paramiko: sanmar_lookup_mainframe_color + auto-resolve fallback
#               (SFTP into ftp.sanmar.com:2200)
RUN pip install --no-cache-dir "pypdf>=4.0" "paramiko>=3.0"

# Stage the entire repo at /srv/sme/. agent-core's bootstrap mirrors this
# tree into the OpenClaw workspace on every boot so the agent can read
# its own code, docs, and configs through workspace-rooted file tools,
# and entrypoint.sh adds /srv/sme to PYTHONPATH so `import sme_tools.*`
# works in skill subprocesses.
COPY . /srv/sme/

# Role files still need to live under /app/roles/{slug}/ — agent-core's
# bootstrap reads from there to materialize the role and decide which
# files to seed into the workspace as SOUL.md / IDENTITY.md / BOOT.md.
COPY roles/ /app/roles/

# SMEs don't need local LLM inference or the image segmentation model.
ENV OLLAMA_ENABLED=false \
    REMBG_ENABLED=false

# Re-use agent-core's entrypoint, supervisord config, healthcheck, and
# exposed port (8080 for the Flask messaging API).
