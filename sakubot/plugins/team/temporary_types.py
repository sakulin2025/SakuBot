from typing import Annotated, Literal, NotRequired, TypedDict

class ReportArgs(TypedDict):
    result: Annotated[str, '本次团队任务的最终成果正文']

class ProgressArgs(TypedDict):
    progress: Annotated[str, '简短阶段进展、阻碍或计划变化，最多2000字，不复述每次工具调用']

class ConfirmationArgs(TypedDict):
    kind: Annotated[Literal['question','confirmation'], 'question 提问；confirmation 请求操作批准']
    question: Annotated[str, '待回答的问题或需批准的操作']
    context: NotRequired[Annotated[str, '主智能体判断所需的背景资料']]
    options: NotRequired[Annotated[list[str], {'description':'可选的建议答案列表','maxItems':20}]]
