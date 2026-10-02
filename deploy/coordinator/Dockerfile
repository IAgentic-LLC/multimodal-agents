FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src \
    EVIDENCE_FIGURES_DIR=/app/figures \
    EDIT_DECISION_LOG=/tmp/capstone-edit-decisions.jsonl \
    TENANT_UPLOAD_DIR=/tmp/uploads \
    LIVE_COMMAND_AUDIT_LOG=/tmp/live-command-audit.jsonl
WORKDIR /app
# ultralytics hard-depends on opencv-python (the GUI build, not
# -headless); it dynamically links libGL/libxcb/libSM/libXext/libXrender,
# none of which exist on this slim base, so it fails at import time
# without them. opencv-python-headless has the same libxcb regression
# right now (opencv-python#1183), so swapping package names doesn't help.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libxcb1 \
    && rm -rf /var/lib/apt/lists/*
# A separate preceding "torch from the cpu index" RUN step does not stick:
# the next pip invocation re-resolves torch from the default index to
# satisfy ultralytics, pulling the full CUDA stack (nvidia-cublas,
# cuda-toolkit, triton, ...) right back in. Resolving everything together
# in one pip call with the cpu wheel index as an extra source is the
# documented fix for this.
# lap is ByteTrack's own real linear-assignment solver
# (model.track(..., tracker="bytetrack.yaml")); ultralytics otherwise
# tries to pip-install it itself at runtime on first real use, which
# fails against this image's real read-only root filesystem
# (CTL-ACCESS-01) - pinning it here avoids that runtime surprise.
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    fastapi==0.119.1 \
    "google-genai==2.25.0" \
    "lap>=0.5.12" \
    langfuse==4.15.6 \
    "nibabel>=5.4.2" \
    "ome-zarr>=0.19.2" \
    pillow==12.3.0 \
    "pydicom>=3.0.2" \
    "pyjwt[crypto]==2.15.0" \
    "python-multipart==0.0.20" \
    "scikit-image>=0.26.0" \
    torch \
    torchvision \
    "ultralytics>=8.4.171" \
    "uvicorn[standard]==0.38.0" \
    "zarr>=3.4.0"
COPY src ./src
COPY evidence-figures ./figures
# YOLO("yolo11n.pt") resolves this relative path against the real
# process cwd (/app) and, if missing, tries to download it there -
# which fails on this image's real read-only root filesystem
# (CTL-ACCESS-01). Bundling the real weights file at build time avoids
# a runtime download entirely, the same real tradeoff already made for
# evidence-figures above.
COPY yolo11n.pt ./yolo11n.pt
RUN useradd --system --uid 10003 --no-create-home coordinator
USER 10003
EXPOSE 8000
CMD ["uvicorn", "multimodal_agents.orchestration_api:app", "--host", "0.0.0.0", "--port", "8000"]
