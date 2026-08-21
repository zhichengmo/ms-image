FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# The repository root remains the build context so the single prompt asset
# tree and root-level environment/configuration files stay available.  The
# Dockerfile itself lives with the Runtime source under apps/runtime.
# Copy requirements first to leverage Docker cache.
COPY apps/runtime/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the one Runtime service root into the repository-root namespace.
RUN mkdir -p apps/runtime
COPY apps/__init__.py ./apps/__init__.py
COPY apps/runtime ./apps/runtime
COPY prompts ./prompts
# Keep only the committed, non-secret qualification artifacts used by Runtime
# config; do not copy the rest of the repository's artifact archive.
COPY docs/artifacts/ai-provider-transport-qualification.v1.json ./docs/artifacts/ai-provider-transport-qualification.v1.json
COPY docs/artifacts/ai-provider-qualification.v1.json ./docs/artifacts/ai-provider-qualification.v1.json

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000 8001

# Command to run the application
CMD ["uvicorn", "apps.runtime.main:app", "--host", "0.0.0.0", "--port", "8000"]
