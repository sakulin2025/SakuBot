"""Bounded live console events; durable conversation remains in Store.events."""
import asyncio
import time


class Live:
    def __init__(self):
        self.clients = set()
        self.sequence = 0
        self.models = {}

    def publish(self, kind, **data):
        self.sequence += 1
        event = {'type': kind, 'sequence': self.sequence, 'at': time.time(), **data}
        if kind == 'model.started':
            self.models[data['request_id']] = {**data, 'content': '', 'status': 'running'}
        elif kind == 'model.delta':
            state = self.models.get(data['request_id'])
            if state:
                state['content'] = (state['content'] + data.get('text', ''))[-200000:]
        elif kind in ('model.completed', 'model.failed'):
            state = self.models.get(data['request_id'])
            if state:
                state['status'] = 'done' if kind.endswith('completed') else 'failed'
        elif kind in ('run.completed', 'run.failed'):
            self.models = {key: value for key, value in self.models.items() if value.get('run_id') != data['run_id']}
        while len(self.models) > 64:
            self.models.pop(next(iter(self.models)))
        for queue in tuple(self.clients):
            if queue.full():
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait({'type': 'resync', 'sequence': self.sequence})
            else:
                queue.put_nowait(event)

    def subscribe(self):
        queue = asyncio.Queue(maxsize=256)
        self.clients.add(queue)
        return queue
