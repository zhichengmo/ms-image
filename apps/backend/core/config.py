from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
import os
from pathlib import Path
from dotenv import dotenv_values, find_dotenv, load_dotenv

from apps.backend.core.reference_env import read_reference_env, reference_env_path

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
    # The HD integration is outside the Runtime primary/evaluation boundary;
    # keep it opt-in so importing the Runtime does not allocate a third pool.
    MYSQL_HD_ENABLED: bool = False
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

    IMAGING_REQUIRED_SCOPE: str = "imaging:run"

    # Admin JWT settings
    ADMIN_ALGORITHM: str = "HS256"
    ADMIN_SECRET_KEY: str = ""
    ADMIN_JWT_ISSUER: str = "ms-image-admin"
    ADMIN_JWT_AUDIENCE: str = "ms-image-admin-api"
    ADMIN_REQUIRED_SCOPE: str = "xray:admin:read"
    ADMIN_REQUIRED_WRITE_SCOPE: str = "xray:admin:write"
    EVALUATION_READ_SCOPE: str = "xray:evaluation:read"
    EVALUATION_WRITE_SCOPE: str = "xray:evaluation:write"
    # Compatibility alias for older configuration consumers.
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
                # The source lives below apps/backend while the container
                # packages it below /app.  Find the first existing key along
                # the runtime/repository parent chain without changing the
                # configured relative path contract.
                key_path = next(
                    (
                        parent / key_path
                        for parent in Path(__file__).resolve().parents
                        if (parent / key_path).is_file()
                    ),
                    key_path,
                )
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
    IMAGING_BROKER_EXCHANGE: str = "imaging.v1"
    IMAGING_BROKER_QUEUE: str = "imaging.image.validate"
    IMAGING_BROKER_ROUTING_KEY: str = "imaging.image.validate"
    IMAGING_BROKER_DLQ: str = "imaging.image.validate.dlq"
    IMAGING_RELAY_POLL_SECONDS: float = 1.0
    IMAGING_RELAY_LEASE_SECONDS: int = 120
    IMAGING_RELAY_HEARTBEAT_PATH: str = "/tmp/ms-image-imaging-relay.heartbeat"
    IMAGING_WORKER_LEASE_SECONDS: int = 120
    IMAGING_WORKER_MAX_ATTEMPTS: int = 5
    # A worker handles one leased message at a time by default.  Scale with
    # replicas before increasing this value so queue ownership stays clear.
    IMAGING_WORKER_CONCURRENCY: int = Field(default=1, ge=1)
    EVALUATION_BROKER_EXCHANGE: str = "evaluation.v1"
    EVALUATION_BROKER_QUEUE: str = "evaluation.job.execute"
    EVALUATION_BROKER_ROUTING_KEY: str = "evaluation.job.execute"
    EVALUATION_BROKER_DLQ: str = "evaluation.job.dlq"
    EVALUATION_RELAY_POLL_SECONDS: float = 1.0
    EVALUATION_RELAY_LEASE_SECONDS: int = 120
    EVALUATION_RELAY_HEARTBEAT_PATH: str = "/tmp/ms-image-evaluation-relay.heartbeat"
    EVALUATION_WORKER_LEASE_SECONDS: int = 120
    EVALUATION_WORKER_MAX_ATTEMPTS: int = 5
    # Keep offline Evaluation processing in the same single-lane contract as
    # Imaging unless an explicitly qualified scale-out plan is available.
    EVALUATION_WORKER_CONCURRENCY: int = Field(default=1, ge=1)
    READINESS_TIMEOUT_SECONDS: float = 3.0

    # Runtime operational alerts. A zero threshold disables that rule;
    # OPERATIONAL_ALERTS_ENABLED disables the whole projection.
    OPERATIONAL_ALERTS_ENABLED: bool = True
    OPERATIONAL_ALERT_LEASE_COUNT_THRESHOLD: int = Field(default=1, ge=0)
    OPERATIONAL_ALERT_ACTIVE_AGE_SECONDS: int = Field(default=300, ge=0)
    OPERATIONAL_ALERT_AI_UNKNOWN_AGE_SECONDS: int = Field(default=300, ge=0)
    OPERATIONAL_ALERT_QUEUE_DEPTH: int = Field(default=100, ge=0)
    OPERATIONAL_ALERT_DLQ_DEPTH: int = Field(default=1, ge=0)
    OPERATIONAL_ALERT_CONSUMER_MINIMUM: int = Field(default=1, ge=0)
    OPERATIONAL_ALERT_MISSING_ROWS: int = Field(default=1, ge=0)
    OPERATIONAL_ALERT_INVALID_COMPARISONS: int = Field(default=1, ge=0)
    OPERATIONAL_ALERT_COVERAGE_LOSS: int = Field(default=1, ge=0)
    OPERATIONAL_ALERT_TECHNICAL_FAILURES: int = Field(default=1, ge=0)
    OPERATIONAL_ALERT_ARTIFACT_DRIFT: int = Field(default=1, ge=0)

    # Prompt runtime and Nacos Prompt settings intentionally use the exact
    # ms-ai-fast deployment contract.  ms-image reads Nacos only in the control
    # plane; Workers render the already-frozen Prompt snapshot.
    PROMPT_RUNTIME_URL: str = ""
    PROMPT_RUNTIME_API_KEY: str = ""
    PROMPT_RUNTIME_ENV: str = "prod"
    PROMPT_RUNTIME_CALLER_SERVICE: str = "ms-image"
    PROMPT_RUNTIME_TIMEOUT_SECONDS: float = Field(30.0, gt=0, allow_inf_nan=False)
    PROMPT_RUNTIME_PROVIDER: str = "nacos"
    PROMPT_SERVICE_CODE: str = "ms-image"
    NACOS_SERVER_ADDR: str = ""
    NACOS_CONTEXT_PATH: str = "/nacos"
    NACOS_USERNAME: str = ""
    NACOS_PASSWORD: str = ""
    NACOS_NAMESPACE_ID: str = ""
    NACOS_PROMPT_NAMESPACE_ID: str = ""
    NACOS_PROMPT_VERSION: str = ""
    NACOS_PROMPT_LABEL: str = ""
    NACOS_PROMPT_TIMEOUT_SECONDS: float = Field(10.0, gt=0, allow_inf_nan=False)

    # OpenAI-compatible ms-ai-platform runtime.  This is the same contract used
    # by ms-ai-fast; there is no separate secret_ref resolver or response-store
    # encryption selector in the request path.
    AI_PLATFORM_OPENAI_BASE_URL: str = ""
    AI_PLATFORM_API_KEY: str = ""
    AI_PLATFORM_TIMEOUT_SECONDS: float = Field(120.0, gt=0, allow_inf_nan=False)

    # Attempt reconciliation is an ms-image durable-state concern, not an
    # alternative Provider transport contract.
    AI_ATTEMPT_RECONCILE_LEASE_SECONDS: int = Field(default=120, ge=30, le=900)
    AI_ATTEMPT_RECONCILE_RETRY_SECONDS: int = Field(default=300, ge=30, le=86400)

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


    @model_validator(mode="after")
    def validate_ai_platform_profile(self):
        platform_url = self.AI_PLATFORM_OPENAI_BASE_URL.strip()
        platform_key = self.AI_PLATFORM_API_KEY.strip()
        if bool(platform_url) != bool(platform_key):
            raise ValueError(
                "AI_PLATFORM_OPENAI_BASE_URL 与 AI_PLATFORM_API_KEY 必须成组配置"
            )
        return self

    @property
    def ai_platform_configured(self) -> bool:
        return bool(
            self.AI_PLATFORM_OPENAI_BASE_URL.strip()
            and self.AI_PLATFORM_API_KEY.strip()
        )

    def require_ai_platform_profile(self) -> None:
        if not self.ai_platform_configured:
            raise RuntimeError(
                "ms-ai-platform 配置不完整：请设置 "
                "AI_PLATFORM_OPENAI_BASE_URL 与 AI_PLATFORM_API_KEY"
            )

    class Config:
        case_sensitive = True
        # Keep the worker's file-backed configuration source aligned with
        # ms-ai-fast. Process environment variables still take precedence.
        env_file = '.env'
        env_file_encoding = 'utf-8'
        extra = 'ignore'


settings = Settings()
