import contextvars

current_chain = contextvars.ContextVar("automation_chain", default=[])
