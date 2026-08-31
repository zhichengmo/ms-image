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
# Dockerfile itself lives with the shared backend workspace under apps/backend.
# Copy requirements first to leverage Docker cache.
COPY apps/backend/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# The image is shared by the three application entrypoints.  Keep their
# source beneath the repository-root namespace so all fully-qualified imports
# resolve the same way in a container and in local development.
COPY apps ./apps
COPY prompts ./prompts
# Evaluation Control readiness imports the frozen schema contract, and the
# one-shot evaluation-migrate service runs this Alembic environment directly.
COPY alembic_evaluation.ini ./alembic_evaluation.ini
COPY alembic_evaluation_migrations ./alembic_evaluation_migrations
# Keep only the committed, non-secret qualification artifacts used by Runtime
# config; do not copy the rest of the repository's artifact archive.
COPY docs/artifacts/ai-provider-transport-qualification.v1.json ./docs/artifacts/ai-provider-transport-qualification.v1.json
COPY docs/artifacts/ai-provider-qualification.v1.json ./docs/artifacts/ai-provider-qualification.v1.json

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000 8001

# Command to run the application
CMD ["uvicorn", "apps.backend.services.runtime.main:app", "--host", "0.0.0.0", "--port", "8000"]
