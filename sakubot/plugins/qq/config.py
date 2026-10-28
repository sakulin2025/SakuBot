import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from urllib.parse import urlsplit


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    owner_id: str = ''
    napcat_ws: str = 'ws://napcat:13001'
    napcat_token: str = ''
    image_model_id: str = ''
    speech_recognition: str = 'unimplemented'
    reply_split_enabled: bool = True
    reply_split_regex: str = '。|'
    reply_remove_regex: str = '。'
    reply_trim: bool = True
    reply_merge_newlines: bool = True
    reply_interval_min: float = Field(3, ge=0, allow_inf_nan=False)
    reply_interval_max: float = Field(5, ge=0, allow_inf_nan=False)

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
        return self


    @field_validator('owner_id', mode='before')
    @classmethod
    def owner(cls, value):
        value = str(value).strip()
        if value and (not value.isdigit() or int(value) <= 0):
            raise ValueError('主人 QQ 必须是有效数字 ID')
        return value

    @field_validator('napcat_ws')
    @classmethod
    def url(cls, value):
        if not value:
            return ''
        url = urlsplit(value)
        if url.scheme not in ('ws', 'wss') or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('WebSocket 地址格式不正确')
        return value.rstrip('/')
