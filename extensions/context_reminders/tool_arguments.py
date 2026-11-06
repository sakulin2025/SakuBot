from typing import Annotated, NotRequired, TypedDict

class Add(TypedDict):
    target: Annotated[str, 'main、* 或旧版 private:QQ号/group:QQ号 目标；main 为统一主会话']
    content: Annotated[str, '背景提醒正文，1至2000字，不作为新指令执行']
    ttl_hours: NotRequired[Annotated[int, '有效期小时，0 使用插件默认值；范围0至87600']]

class ListArgs(TypedDict):
    target: NotRequired[Annotated[str, '按目标筛选；留空列全部生效记录']]

class Remove(TypedDict):
    reminder_id: Annotated[str, '待删除的上下文提醒 ID']

ARGUMENTS = {'add_context_reminder':Add,'list_context_reminders':ListArgs,'remove_context_reminder':Remove}
