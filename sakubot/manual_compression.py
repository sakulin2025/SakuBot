"""Exclusive, non-conversational maintenance of the main Agent's context."""
import asyncio
import json
import time
import uuid

from .plugin import Invocation
from .store import encode


def begin(runtime):
    instance = runtime.agents.get('main')
    if runtime.current_run or instance.busy or instance.resetting or runtime.control.quiescing():
        raise RuntimeError('主智能体正在运行，请稍后压缩')
    if runtime.store.one("SELECT id FROM events WHERE kind='wake' AND target='main' AND status='pending' AND (expires=0 OR expires>?) LIMIT 1", (time.time(),)):
        raise RuntimeError('主对话有待处理消息，请稍后压缩')
    memo, history = runtime.main_history()
    if not history and not memo.get('text'):
        raise ValueError('没有可压缩的上下文')
    run_id = uuid.uuid4().hex
    inv = Invocation(run_id, 'main', instance=instance)
    profile = runtime.prepare_agent(inv)
    _, model = inv.metadata['_model_settings'].selected_model(model_id=inv.model_id)
    if not model or not model.capabilities.text:
        raise ValueError('请先配置支持文本的主智能体模型')
    from .runtime import SYSTEM
    messages = [{'role': 'system', 'content': profile['prompt'] + '\n' + SYSTEM}]
    if memo.get('text'):
        messages.append({'role': 'assistant', 'content': '历史上下文摘要：\n' + memo['text'], '_summary': True})
    messages.extend(history)
    # Use an existing chat entry as the process anchor; no artificial wake/user message.
    anchor = runtime.store.one("SELECT id FROM events WHERE id>? AND coalesce(json_extract(meta,'$.exclude_main'),0)=0 AND (kind!='context' OR coalesce(json_extract(meta,'$.exclude_context'),0)=0) ORDER BY id DESC LIMIT 1", (runtime.chat.boundary()['cutoff'],))
    if not anchor:
        raise ValueError('没有可压缩的主对话')
    event_id = anchor['id']
    trace = {'manual_compression': True, 'model_id': inv.model_id, 'compressions': []}
    runtime.store.execute("INSERT INTO runs VALUES (?,?,?,NULL,'running',?,'')", (run_id, event_id, time.time(), encode(trace)))
    runtime.current_run = {'id': run_id, 'event_id': event_id, 'started': time.time(), 'kind': 'compression', 'send_result_to_source': True}
    job = asyncio.create_task(execute(runtime, messages, inv))
    runtime.compression.manual_job = job
    runtime.jobs.append(job)
    def finished(task):
        if task in runtime.jobs:
            runtime.jobs.remove(task)
    job.add_done_callback(finished)
    return {'run_id': run_id, 'status': 'running'}


def calibration(runtime, model_id):
    for row in runtime.store.rows('SELECT trace FROM runs ORDER BY started DESC LIMIT 20'):
        trace = json.loads(row['trace'] or '{}')
        if trace.get('model_id') != model_id:
            continue
        requests, usages = trace.get('api_requests', []), trace.get('usage', [])
        if requests and usages and len(usages) >= len(requests):
            used = usages[-1].get('prompt_tokens')
            body = requests[-1].get('body', {})
            size = runtime.compression.estimate(body.get('messages', []), body.get('tools'))
            if isinstance(used, (int, float)) and used > 0 and size:
                return min(1, max(.05, used / size))
    return .25


async def execute(runtime, messages, inv):
    status, error = 'done', ''
    runtime.conversation.process('run.started', run_id=inv.run_id, event_id=runtime.current_run['event_id'], agent_id='main')
    try:
        async with inv.instance.lock:
            selected = inv.metadata['_model_settings'].selected_model(model_id=inv.model_id)[1]
            tools = [tool.schema() for tool in runtime.registry.available(inv)] if selected.capabilities.tools else []
            await runtime.refresh_capabilities(messages, inv)
            ratio = calibration(runtime, inv.model_id)
            await runtime.compression.compact(messages, inv, tools, force=True)
            row = runtime.store.one('SELECT trace FROM runs WHERE id=?', (inv.run_id,))
            trace = json.loads(row['trace'])
            trace['context_after'] = round(runtime.compression.estimate(messages, tools) * ratio)
            runtime.store.execute('UPDATE runs SET trace=? WHERE id=?', (encode(trace), inv.run_id))
    except BaseException as exc:
        status = 'interrupted' if isinstance(exc, asyncio.CancelledError) else 'failed'
        error = str(exc)[:500] if isinstance(exc, (RuntimeError, ValueError)) else type(exc).__name__
        runtime.store.log('error', 'agents', 'context.manual_compression.failed', run_id=inv.run_id, data={'error': error})
    finally:
        runtime.store.execute('UPDATE runs SET status=?,finished=?,error=? WHERE id=?', (status, time.time(), error, inv.run_id))
        runtime.conversation.process('run.completed' if status == 'done' else 'run.failed', run_id=inv.run_id, agent_id='main', error=error)
        if runtime.current_run and runtime.current_run['id'] == inv.run_id:
            runtime.current_run = None
        runtime.compression.manual_job = None
        runtime.changed.set()
