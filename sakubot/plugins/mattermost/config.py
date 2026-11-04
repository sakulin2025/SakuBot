import re
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_url: str = ''
    token: str = ''
    channel_ids: list[str] = Field(default_factory=list, max_length=100)
    respond_all_direct: bool = False
    legacy_owner: str = ''
    slash_enabled: bool = False
    slash_base_url: str = ''
    image_model_id: str = ''
    reply_split_enabled: bool = True
    reply_split_regex: str = '。|'
    reply_remove_regex: str = '。'
    reply_trim: bool = True
    reply_merge_newlines: bool = True
    reply_interval_min: float = Field(3, ge=0, allow_inf_nan=False)
    reply_interval_max: float = Field(5, ge=0, allow_inf_nan=False)

    @staticmethod
    def validate_slash_base(value):
        if not isinstance(value, str):
            raise ValueError('SakuBot 基础地址须为字符串')
        value = value.strip()
        if not value:
            return ''
        try:
            parts = urlsplit(value)
            parts.port
        except ValueError:
            raise ValueError('SakuBot 基础地址格式无效') from None
        if (len(value) > 2000 or parts.scheme not in ('http', 'https') or not parts.hostname
                or parts.username or parts.password or parts.query or parts.fragment
                or any(char.isspace() for char in value)):
            raise ValueError('请填写有效的 http(s):// SakuBot 基础地址')
        if parts.path.rstrip('/').endswith('/hooks/mattermost/slash'):
            raise ValueError('只需填写 SakuBot 基础地址，不要包含 /hooks/mattermost/slash')
        return value.rstrip('/') + '/'

    @staticmethod
    def callback_url(base):
        base = Settings.validate_slash_base(base)
        return base + 'hooks/mattermost/slash' if base else ''

    @model_validator(mode='before')
    @classmethod
    def migrate_slash_address(cls, value):
        if not isinstance(value, dict):
            return value
        value = dict(value)
        old_owner = value.pop('owner', '')
        if old_owner and not value.get('channel_ids'):
            value['legacy_owner'] = value.get('legacy_owner') or old_owner
        value.pop('slash_tokens', None)
        old = value.pop('slash_callback_url', '')
        if old and not value.get('slash_base_url'):
            suffix = '/hooks/mattermost/slash'
            if not isinstance(old, str) or not old.rstrip('/').endswith(suffix):
                raise ValueError('旧版 Slash 请求地址格式无效')
            value['slash_base_url'] = old.rstrip('/')[:-len(suffix)] + '/'
        return value

    @field_validator('channel_ids')
    @classmethod
    def channels_valid(cls, values):
        if any(not re.fullmatch(r'[a-z0-9]{26}', value) for value in values):
            raise ValueError('频道 ID 须为 26 位小写字母或数字')
        if len(set(values)) != len(values):
            raise ValueError('频道 ID 不能重复')
        return values

    @field_validator('slash_base_url')
    @classmethod
    def callback_valid(cls, value):
        return cls.validate_slash_base(value)

    @field_validator('reply_split_regex', 'reply_remove_regex')
    @classmethod
    def regex(cls, value):
        try:
            re.compile(value)
        except re.error:
            raise ValueError('正则表达式无效') from None
        return value

    @model_validator(mode='after')
    def intervals(self):
        if self.reply_interval_max < self.reply_interval_min:
            raise ValueError('最大间隔不能小于最小间隔')
        # Managed commands keep their individual tokens in the private command journal.
        return self
