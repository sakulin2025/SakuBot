import json
import os
import secrets
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .wake_prompt import DEFAULT as DEFAULT_WAKE_PROMPT, CHANGE_DEFAULT, RISK_DEFAULT, LEGACY_CHANGE_DEFAULT, validate_template, validate_change_template


def http_url(value):
    url = urlsplit(value)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("API 地址不正确")
    return value.rstrip("/")


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], pattern=r"^[A-Za-z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=100)
    api_base: str
    api_key: str = ""
    enabled: bool = True

    @field_validator("api_base")
    @classmethod
    def base(cls, value):
        return http_url(value)


class Capabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: bool = True
    image: bool = False
    audio: bool = False
    tools: bool = True
    embedding: bool = False
    asr: bool = False
    tts: bool = False
    streaming_input: bool = False
    streaming_output: bool = False
    realtime: bool = False


class ModelMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context_window: int = Field(0, ge=0, le=100000000)
    capabilities: dict[str, bool] = Field(default_factory=dict)
    source: str = ""
    fetched_at: float = 0


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], pattern=r"^[A-Za-z0-9_-]{1,64}$")
    provider_id: str
    model_id: str = Field(min_length=1, max_length=300)
    name: str = Field(default="", max_length=100)
    enabled: bool = True
    capabilities: Capabilities = Field(default_factory=Capabilities)
    extra_body: dict = Field(default_factory=dict)
    context_window: int = Field(0, ge=0, le=100000000)
    embedding_dimensions: int = Field(0, ge=0, le=65536)
    metadata: ModelMetadata = Field(default_factory=ModelMetadata)
    speech_api: Literal['openai', 'mimo'] = 'openai'
    speech_sample_rate: int = Field(24000, ge=8000, le=48000)

    @field_validator("extra_body")
    @classmethod
    def body(cls, value):
        if set(value) & {"model", "messages", "stream", "tools"}:
            raise ValueError("请求参数不能覆盖 model、messages、stream 或 tools")
        serialized = json.dumps(value, allow_nan=False)
        if len(serialized) > 30000:
            raise ValueError("请求参数过大")
        for key in ("max_tokens", "max_completion_tokens"):
            if key in value and (type(value[key]) is not int or value[key] < 1):
                raise ValueError("输出 Token 数必须为正整数")
        if "max_tokens" in value and "max_completion_tokens" in value:
            raise ValueError("不能同时设置两种输出 Token 参数")
        return value

    def effective_window(self):
        return self.context_window or self.metadata.context_window


class ConversationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal['intelligent'] = 'intelligent'
    targets: list[str] = Field(default_factory=list, max_length=100)
    tool_events: bool = False
    wake_insertion: Literal['queue', 'next_boundary', 'same_source_boundary'] = 'queue'
    same_source_priority: bool = False
    untrusted_source_template: str = RISK_DEFAULT
    source_change_enabled: bool = True
    source_change_mode: Literal['context', 'temporary'] = 'context'
    source_change_template: str = CHANGE_DEFAULT

    @model_validator(mode='before')
    @classmethod
    def follow_source_only(cls, value):
        if isinstance(value, dict):
            value = {**value, 'mode': 'intelligent', 'targets': []}
            if value.get('source_change_template') == LEGACY_CHANGE_DEFAULT:
                value['source_change_template'] = CHANGE_DEFAULT
            return value
        return value

    @field_validator('untrusted_source_template')
    @classmethod
    def validate_source_risk(cls, value):
        return validate_template(value)

    @field_validator('source_change_template')
    @classmethod
    def validate_source_change(cls, value):
        return validate_change_template(value)


class AgentPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    persona_id: str = ""
    model_id: str = ""
    @model_validator(mode="before")
    @classmethod
    def global_compression(cls, value):
        if isinstance(value, dict):
            return {key: item for key, item in value.items() if key not in ("compression_enabled", "compression_threshold")}
        return value


class ProgressReminderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    tool_threshold: int = Field(5, ge=1, le=1000)
    seconds_threshold: float = Field(30, ge=1, le=86400)
    mode: Literal['remind', 'require'] = 'remind'
    prompt: str = Field(
        '请使用 message_send 向当前主会话源简短说明刚刚完成了什么，以及接下来准备做什么。无需罗列工具，不要泄露当前会话源不应获知的信息。',
        min_length=1, max_length=10000)


class RequestRetrySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_retries: int = Field(3, ge=0, le=10)
    retry_notice: str = Field("刚刚开小差了，让我尝试重新集中注意力", max_length=2000)
    exhausted_notice: str = Field("（睡着了）", max_length=2000)
    fatal_notice: str = Field("没精力理你了…", max_length=2000)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    providers: list[ProviderConfig] = Field(default_factory=list)
    models: list[ModelConfig] = Field(default_factory=list)
    main_model_id: str = ""
    lightweight_model_id: str = ""
    main_persona_id: str = "default"
    max_steps: int = Field(16, ge=1, le=64)
    context_chars: int = Field(48000, ge=8000, le=200000)
    plugins: list[str] = Field(default_factory=list)

    @field_validator('plugins')
    @classmethod
    def plugin_ids(cls, value):
        from .components import optional_ids
        return optional_ids(value)

    wake_prompt_template: str = DEFAULT_WAKE_PROMPT

    @field_validator("wake_prompt_template")
    @classmethod
    def wake_prompt_valid(cls, value):
        return validate_template(value)

    progress_reminder: ProgressReminderSettings = Field(default_factory=ProgressReminderSettings)
    request_retry: RequestRetrySettings = Field(default_factory=RequestRetrySettings)
    compression_notice: str = Field("稍等，脑子太乱了，给我点时间让我整理一下思绪", max_length=2000)
    compression_enabled: bool = True
    compression_threshold: float = Field(0.8, ge=0.1, le=0.95)
    conversation: ConversationSettings = Field(default_factory=ConversationSettings)
    agent_concurrency: int = Field(3, ge=1, le=8)
    agent_settings: dict[str, AgentPreferences] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def legacy_model(cls, value):
        if not isinstance(value, dict):
            return value
        value = dict(value)
        if "subagent_concurrency" in value:
            value.setdefault("agent_concurrency", value.pop("subagent_concurrency"))
        if "plugins" in value:
            value["plugins"] = list(dict.fromkeys("team" if name == "subagents" else name for name in value["plugins"]))
        for retired in ("persona", "group_mode", "group_allowlist"):
            value.pop(retired, None)
        legacy = {key: value.pop(key) for key in ("llm_base", "llm_key", "llm_model", "lightweight_model") if key in value}
        if legacy and not value.get("providers") and (legacy.get("llm_key") or legacy.get("llm_model")):
            value["providers"] = [{"id": "legacy-provider", "name": "原供应商", "api_base": legacy.get("llm_base") or "https://api.deepseek.com/v1", "api_key": legacy.get("llm_key", "")}]
            value["models"] = [{"id": "legacy-main", "provider_id": "legacy-provider", "model_id": legacy.get("llm_model") or "deepseek-chat"}]
            value["main_model_id"] = "legacy-main"
            if legacy.get("lightweight_model"):
                value["models"].append({"id": "legacy-light", "provider_id": "legacy-provider", "model_id": legacy["lightweight_model"]})
                value["lightweight_model_id"] = "legacy-light"
        return value

    @model_validator(mode="after")
    def catalog(self):
        provider_ids = [item.id for item in self.providers]
        model_ids = [item.id for item in self.models]
        if len(set(provider_ids)) != len(provider_ids) or len(set(model_ids)) != len(model_ids):
            raise ValueError("供应商或模型 ID 重复")
        if any(item.provider_id not in provider_ids for item in self.models):
            raise ValueError("模型关联的供应商不存在")
        if any(identifier and identifier not in model_ids for identifier in (self.main_model_id, self.lightweight_model_id)):
            raise ValueError("所选模型不存在")
        return self

    def ready(self):
        return self.enabled and self.model_ready()

    def selected_model(self, lightweight=False, model_id=None):
        main = self.agent_settings.get("main")
        identifier = model_id if model_id is not None else (
            self.lightweight_model_id if lightweight and self.lightweight_model_id else
            (main.model_id if main and main.model_id else self.main_model_id))
        model = next((item for item in self.models if item.id == identifier and item.enabled and item.capabilities.text), None)
        provider = next((item for item in self.providers if model and item.id == model.provider_id and item.enabled), None)
        return (provider, model) if provider and model else (None, None)

    def selected_embedding_model(self, model_id):
        model = next((item for item in self.models if item.id == model_id and item.enabled and item.capabilities.embedding), None)
        provider = next((item for item in self.providers if model and item.id == model.provider_id and item.enabled), None)
        return (provider, model) if provider and model else (None, None)

    def selected_speech_model(self, model_id, capability):
        if capability not in ('asr', 'tts'):
            raise ValueError('语音能力必须为ASR或TTS')
        model = next((item for item in self.models if item.id == model_id and item.enabled
                      and getattr(item.capabilities, capability)), None)
        provider = next((item for item in self.providers if model and item.id == model.provider_id and item.enabled), None)
        if not model or not provider:
            raise ValueError('未选择已启用的' + capability.upper() + '模型')
        return provider, model

    def model_ready(self):
        return self.selected_model()[0] is not None


class Config:
    def __init__(self):
        self.root = Path(os.environ.get("SAKUBOT_DATA", "./data"))
        plugin_root = self.root / 'plugins'
        self.fresh_install = (not any((self.root / name).exists() for name in ('config.json', 'sakubot.sqlite3', 'admin_token'))
            and (not plugin_root.exists() or (plugin_root.is_dir() and not any(plugin_root.iterdir()))))
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for directory in ('plugins', 'plugin_data'):
            (self.root / directory).mkdir(mode=0o700, exist_ok=True)
        self.path = self.root / "config.json"
        raw = json.loads(self.path.read_text()) if self.path.exists() else {}
        legacy_processing = raw.pop("message_processing", None)
        if isinstance(legacy_processing, dict):
            legacy_path = self.root / 'plugin_data' / 'legacy_message_processing.json'
            if not legacy_path.exists():
                self.atomic(legacy_path, json.dumps(legacy_processing, ensure_ascii=False, indent=2) + "\n")
            self.atomic(self.path, json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
        self.legacy_persona = raw.get("persona", "")
        self.settings = Settings.model_validate(raw)
        if 'plugins' in raw and raw['plugins'] != self.settings.plugins:
            raw['plugins'] = self.settings.plugins
            self.atomic(self.path, json.dumps(raw, ensure_ascii=False, indent=2) + '\n')
        token_path = self.root / "admin_token"
        if not token_path.exists():
            self.atomic(token_path, secrets.token_urlsafe(32) + "\n")
        self.token = token_path.read_text().strip()
        if not self.token:
            raise RuntimeError("admin_token 为空，请修复文件")

    @staticmethod
    def atomic(path, content):
        temp = path.with_suffix(".tmp")
        with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as file:
            file.write(content)
        os.replace(temp, path)

    def save(self, settings):
        if settings.enabled and not settings.ready():
            raise ValueError("启用前请选择已启用的主模型")
        self.atomic(self.path, settings.model_dump_json(indent=2) + "\n")
        self.settings = settings

    def public(self):
        data = self.settings.model_dump()
        for provider in data["providers"]:
            provider["api_key_configured"] = bool(provider.pop("api_key"))
        for model, record in zip(self.settings.models, data["models"]):
            record["effective_context_window"] = model.effective_window()
        data["main_session"] = {"type": "main"}
        return data
