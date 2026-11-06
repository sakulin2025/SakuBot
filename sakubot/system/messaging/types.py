from typing import Annotated, TypedDict


class SendResult(TypedDict):
    submitted: Annotated[bool, '消息是否提交；true 不保证所有远端已经送达']
    response_id: Annotated[str, '本条主动消息的响应 ID']
    parts: Annotated[int, '提交的消息内容块数量']
