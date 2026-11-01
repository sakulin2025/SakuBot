import re
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_url: str = ''
    token: str = ''
    owner: str = ''
    image_model_id: str = ''
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
