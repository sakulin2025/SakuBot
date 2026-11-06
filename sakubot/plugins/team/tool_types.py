"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class Persona(TypedDict, total=False):
    prompt: Required[Annotated[str, '插件保存的自管理人格提示词']]
    visible_plugins: Annotated[list[str] | None, '可见插件 ID，null 继承默认']

class _Member(TypedDict, total=False):
    id: Required[Annotated[str, '成员本地 ID']]
    name: Required[Annotated[str, '成员名称']]
    description: Required[Annotated[str, '成员职责']]
    persona: Annotated[Persona, '自管理人格，完整读取时可见']
    model_id: Annotated[str, '插件模型默认值']
    agent: Annotated[DynamicObject, '框架实际生效的模型、状态和人格来源']
    available_plugins: Annotated[list[DynamicObject], '可选插件 ID 和可用状态']
Member: TypeAlias = Annotated[_Member, {'additionalProperties': True}]

class MemberSummary(TypedDict, total=False):
    id: Required[Annotated[str, '完整智能体 ID']]
    name: Required[Annotated[str, '名称']]
    description: Required[Annotated[str, '职责']]
    ready: Required[Annotated[bool, '是否可运行']]
    busy: Required[Annotated[bool, '是否正在工作']]
    persona_source: Required[Annotated[str, '人格来源']]
    persona_name: Required[Annotated[str, '人格名称']]
    model_name: Required[Annotated[str, '生效模型名称']]

class Delegated(TypedDict, total=False):
    id: Required[Annotated[str, '团队任务 ID']]
    agent_id: Required[Annotated[str, '执行成员 ID']]
    agent_name: Required[Annotated[str, '成员名称']]
    status: Required[Annotated[str, 'pending 等队列状态']]
    report: Required[Annotated[str, '任务回报方式']]

class _Task(TypedDict, total=False):
    id: Required[Annotated[str, '任务 ID']]
    status: Required[Annotated[str, '任务状态']]
    updated: Annotated[float, '更新时间 Unix 秒']
    data: Annotated[DynamicObject, '任务目标、成员、进度及结果资料']
    agent_id: Annotated[str, '执行智能体 ID']
Task: TypeAlias = Annotated[_Task, {'additionalProperties': True}]

class Recorded(TypedDict, total=False):
    recorded: Required[Annotated[bool, '结果已记录']]

class Progress(TypedDict, total=False):
    recorded: Required[Annotated[bool, '进度已记录']]
    progress: Required[Annotated[str, '实际保存的进度']]

class _Request(TypedDict, total=False):
    id: Annotated[str, '请求 ID']
    request_id: Annotated[str, '答复的请求 ID']
    agent_id: Annotated[str, '提问成员 ID']
    status: Required[Annotated[str, 'waiting/answered 等状态']]
    kind: Annotated[str, 'question 或 confirmation']
    question: Annotated[str, '问题正文']
    answer: Annotated[str, '答复正文']
    approved: Annotated[bool | None, '确认是否批准；问答类型可为空']
    options: Annotated[list[str], '建议选项']
    created: Annotated[float, '请求创建 Unix 秒']
Request: TypeAlias = Annotated[_Request, {'additionalProperties': True}]

class ConfirmationAnswer(TypedDict):
    request_id: Annotated[str, '已答复的待确认请求 ID']
    kind: Annotated[str, 'question 或 confirmation']
    answer: Annotated[str, '主智能体给出的答复']
    approved: Annotated[bool | None, '是否批准；普通问答可能为 null']

R_team_members: TypeAlias = list[MemberSummary]
R_team_delegate: TypeAlias = Delegated
R_team_tasks: TypeAlias = Task | list[Task]
R_team_create_member: TypeAlias = Member
R_team_get_member: TypeAlias = Member
R_team_update_member: TypeAlias = Member
R_team_requests: TypeAlias = list[Request]
R_team_resolve: TypeAlias = Request
R_team_report_result: TypeAlias = Recorded
R_team_update_progress: TypeAlias = Progress
R_team_wait_confirmation: TypeAlias = ConfirmationAnswer

RESULTS = {'team_members': R_team_members, 'team_delegate': R_team_delegate, 'team_tasks': R_team_tasks, 'team_create_member': R_team_create_member, 'team_get_member': R_team_get_member, 'team_update_member': R_team_update_member, 'team_requests': R_team_requests, 'team_resolve': R_team_resolve, 'team_report_result': R_team_report_result, 'team_update_progress': R_team_update_progress, 'team_wait_confirmation': R_team_wait_confirmation}
