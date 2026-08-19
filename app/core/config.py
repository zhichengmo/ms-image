from pydantic_settings import BaseSettings
import os
from pathlib import Path
from dotenv import dotenv_values, find_dotenv, load_dotenv

from app.core.reference_env import read_reference_env, reference_env_path

load_dotenv(find_dotenv())


def _missing_reference_values(explicit: dict) -> dict:
    """Map only allow-listed legacy settings into the local runtime config.

    This is a local qualification convenience.  The old repository is not
    imported and its .env-01 is never written back to disk or persisted by this
    service.  Explicit process/local ms-image values always win.
    """

    local_path = find_dotenv()
    local = dotenv_values(local_path) if local_path else {}
    reference = read_reference_env(
        path=reference_env_path(),
        keys={
            "ALIYUN_OSS_ENDPOINT",
            "ALIYUN_OSS_BUCKET",
            "RABBITMQ_HOST",
            "RABBITMQ_PORT",
            "RABBITMQ_USERNAME",
            "RABBITMQ_VIRTUAL_HOST",
        },
    )
    present = set(explicit) | set(os.environ) | {
        key for key, value in local.items() if isinstance(value, str) and value.strip()
    }
    mapping = {
        "OSS_ENDPOINT": "ALIYUN_OSS_ENDPOINT",
        "OSS_BUCKET_NAME": "ALIYUN_OSS_BUCKET",
        # The old project names these OSS credentials ALIYUN_*; accept the
        # names only from the current ms-image process environment/local .env.
        # Provider credentials are deliberately not mapped from GEMINI_*.
        "OSS_ACCESS_KEY_ID": "ALIYUN_OSS_ACCESS_KEY_ID",
        "OSS_ACCESS_KEY_SECRET": "ALIYUN_OSS_ACCESS_KEY_SECRET",
        "RABBITMQ_HOST": "RABBITMQ_HOST",
        "RABBITMQ_PORT": "RABBITMQ_PORT",
        "RABBITMQ_USERNAME": "RABBITMQ_USERNAME",
        "RABBITMQ_VIRTUAL_HOST": "RABBITMQ_VIRTUAL_HOST",
    }
    values: dict[str, str] = {}
    for target, source in mapping.items():
        if target in present:
            continue
        source_value = (
            os.environ.get(source)
            or local.get(source)
            or reference.get(source)
        )
        if isinstance(source_value, str) and source_value.strip():
            values[target] = source_value.strip()
    # Secrets are intentionally never projected from the legacy repository.
    # Provider, OSS and RabbitMQ credentials must be supplied explicitly by
    # the process environment or an approved Secret Manager integration.
    return values


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"

    APPLICATION_HOST: str = "localhost"
    APPLICATION_NAME: str = "Ms Image Service"
    APPLICATION_PORT: int = 8000

    ENV: str = "dev"

    GUNICORN_ERROR_LOG_PATH: str = "./logs/gunicorn_error.log"
    LOG_PATH: str = "./logs/"

    MONGO_AUTH_SOURCE: str = "admin"
    MONGO_DB: str = "ms_image"
    MONGO_HOST: str = "localhost"
    MONGO_PASSWORD: str = ""
    MONGO_PORT: str = "27017"
    MONGO_USER: str = "admin"

    # Primary Database settings
    MYSQL_DB: str = "ms_image"
    MYSQL_HOST: str = "localhost"
    MYSQL_PW: str = "password"
    MYSQL_USER: str = "root"
    MYSQL_PORT: str = "3306"
    MYSQL_UNIX_SOCKET: str = ""

    # Isolated Evaluation Database settings
    MYSQL_EVALUATION_DB: str = "ms_image_eval"
    MYSQL_EVALUATION_HOST: str = ""
    MYSQL_EVALUATION_PW: str = ""
    MYSQL_EVALUATION_USER: str = ""
    MYSQL_EVALUATION_PORT: str = ""
    MYSQL_EVALUATION_UNIX_SOCKET: str = ""

    # MS_HD Database settings (optional for HD service integration)
    MYSQL_HD_DB: str = "ms_hd"
    MYSQL_HD_HOST: str = "localhost"
    MYSQL_HD_PW: str = "password"
    MYSQL_HD_USER: str = "root"
    MYSQL_HD_PORT: str = "3306"
    MYSQL_HD_UNIX_SOCKET: str = ""

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    ALGORITHM: str = "RS256"
    SECRET_KEY: str = ""
    API_PRIVATE_KEY: str = ""
    JWT_ISSUER: str = "ms-image"
    JWT_AUDIENCE: str = "ms-image-api"
    # Generic imaging scope; the legacy default preserves current XRay callers.
    IMAGING_REQUIRED_SCOPE: str = "xray:run"
    XRAY_REQUIRED_SCOPE: str = "xray:run"

    # Admin JWT settings
    ADMIN_ALGORITHM: str = "HS256"
    ADMIN_SECRET_KEY: str = ""
    ADMIN_JWT_ISSUER: str = "ms-image-admin"
    ADMIN_JWT_AUDIENCE: str = "ms-image-admin-api"
    ADMIN_REQUIRED_SCOPE: str = "xray:admin:read"
    ADMIN_REQUIRED_WRITE_SCOPE: str = "xray:admin:write"
    EVALUATION_REQUIRED_SCOPE: str = "xray:evaluation:write"
    RSA_PUBLIC_KEY_PATH: str = "rsa_public.pem"
    TENANT_CLAIM: str = "tenant_id"

    def __init__(self, **kwargs):
        fallback_values = _missing_reference_values(kwargs)
        super().__init__(**{**fallback_values, **kwargs})
        # 根据算法类型加载密钥
        if self.ALGORITHM == "RS256" and not self.SECRET_KEY:
            key_path = Path(self.RSA_PUBLIC_KEY_PATH)
            if not key_path.is_absolute():
                key_path = Path(__file__).resolve().parents[2] / key_path
            if key_path.is_file():
                self.SECRET_KEY = key_path.read_text(encoding="utf-8")
            else:
                # Authentication dependencies fail closed when this key is
                # absent; importing the app remains possible for liveness.
                self.SECRET_KEY = ""
        # HS256算法使用环境变量中的SECRET_KEY

    AUTH_DOMAIN: str = "localhost"

    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PASSWORD: str = "password"
    RABBITMQ_PORT: str = "5672"
    RABBITMQ_USERNAME: str = "admin"
    RABBITMQ_VIRTUAL_HOST: str = "/"
    BROKER_ENABLED: bool = False
    CELERY_BROKER_URL: str = ""
    XRAY_BROKER_EXCHANGE: str = "xray.v2"
    XRAY_BROKER_QUEUE: str = "xray.stage.requested"
    XRAY_BROKER_ROUTING_KEY: str = "xray.run.stage.requested"
    XRAY_BROKER_DLQ: str = "xray.stage.dlq"
    XRAY_RELAY_POLL_SECONDS: float = 1.0
    XRAY_RELAY_LEASE_SECONDS: int = 120
    XRAY_WORKER_LEASE_SECONDS: int = 120
    XRAY_WORKER_MAX_ATTEMPTS: int = 5
    IMAGING_BROKER_EXCHANGE: str = "imaging.v1"
    IMAGING_BROKER_QUEUE: str = "imaging.image.validate"
    IMAGING_BROKER_ROUTING_KEY: str = "imaging.image.validate"
    IMAGING_BROKER_DLQ: str = "imaging.image.validate.dlq"
    IMAGING_RELAY_POLL_SECONDS: float = 1.0
    IMAGING_RELAY_LEASE_SECONDS: int = 120
    IMAGING_WORKER_LEASE_SECONDS: int = 120
    IMAGING_WORKER_MAX_ATTEMPTS: int = 5
    EVALUATION_BROKER_EXCHANGE: str = "evaluation.v1"
    EVALUATION_BROKER_QUEUE: str = "evaluation.job.execute"
    EVALUATION_BROKER_ROUTING_KEY: str = "evaluation.job.execute"
    EVALUATION_BROKER_DLQ: str = "evaluation.job.dlq"
    EVALUATION_RELAY_POLL_SECONDS: float = 1.0
    EVALUATION_RELAY_LEASE_SECONDS: int = 120
    EVALUATION_WORKER_LEASE_SECONDS: int = 120
    EVALUATION_WORKER_MAX_ATTEMPTS: int = 5
    READINESS_TIMEOUT_SECONDS: float = 3.0

    # AI transport is selected by the database-backed OpenAI-compatible
    # connection pool.  These are qualification artifacts/secrets only;
    # endpoint/model/key/timeout/max_tokens do not belong in environment vars.
    AI_RECEIPT_SIGNING_KEY: str = ""
    AI_EGRESS_PROOF_SIGNING_KEY: str = ""
    AI_TRANSPORT_QUALIFICATION_ARTIFACT_PATH: str = (
        "docs/artifacts/ai-provider-transport-qualification.v1.json"
    )
    AI_QUALIFICATION_IMAGE_PATHS: str = ""
    AI_QUALIFICATION_ARTIFACT_PATH: str = "docs/artifacts/ai-provider-qualification.v1.json"
    AI_QUALIFICATION_ARTIFACT_SIGNING_KEY: str = ""
    AI_QUALIFICATION_MAX_ATTEMPTS: int = 32
    AI_QUALIFICATION_TENANT_ID: str = "xray-qualification"
    AI_QUALIFICATION_SUBJECT_ID: str = "provider-qualification"
    AI_CONFIG_VERSION: str = ""
    # Isolated qualification-only source fixture contract.  The manifest
    # contains opaque refs, relative paths and expected SHA256; it is never
    # accepted from an API request and is not a production image source.
    AI_SOURCE_IMAGE_MANIFEST_PATH: str = ""
    AI_SOURCE_IMAGE_ROOT: str = ""
    # Compatibility-only hash map. Keys are SHA256(image_url), values are
    # approved opaque source refs. Raw legacy URLs are never persisted.
    AI_LEGACY_IMAGE_REF_MAP_PATH: str = ""
    # Compatibility switch stays false until the Study/ObjectStore gate is
    # deployed and its isolated test-database artifact is approved.
    AI_REQUIRE_FROZEN_STUDY: bool = True

    PROJECT_ENV: str = "development"

    # 阿里云推送服务配置
    ALIBABA_ACCESS_KEY_ID: str = ""
    ALIBABA_ACCESS_KEY_SECRET: str = ""
    ALIBABA_PUSH_APP_KEY_IOS: str = ""
    ALIBABA_PUSH_APP_KEY_ANDROID: str = ""

    # 阿里云OSS配置
    OSS_ACCESS_KEY_ID: str = ""
    OSS_ACCESS_KEY_SECRET: str = ""
    OSS_BUCKET_NAME: str = ""
    OSS_UPLOAD_ENDPOINT: str = ""
    OSS_ENDPOINT: str = ""
    OSS_STORAGE_PROFILE: str = "default"
    OSS_SIGNED_URL_TTL_SECONDS: int = 300

    class Config:
        case_sensitive = True
        env_file = '.env-01'
        env_file_encoding = 'utf-8'


settings = Settings()
