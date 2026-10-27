"""Non-interactive container shell with bounded output and process-group cleanup."""
import asyncio
import json
import os
import signal
import time
import uuid


class Shell:
    def __init__(self, workspace):
        self.workspace = workspace
        self.processes = set()
        self.jobs = {}
        self.tasks = {}
        self.job_dir = workspace.root.parent / 'shell_jobs'
        self.job_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(self.job_dir.glob('*.json'), key=lambda p: p.stat().st_mtime)[-100:]:
            try:
                record = json.loads(path.read_text())
                if record['status'] == 'running':
                    record.update(status='interrupted', finished_at=time.time())
                    self._save(record)
                self.jobs[record['id']] = record
            except (ValueError, KeyError, OSError, TypeError):
                continue

    def _save(self, record):
        path = self.job_dir / (record['id'] + '.json')
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)

    def _validate(self, command, cwd, timeout, maximum):
        if not isinstance(command, str) or not command.strip() or len(command) > 200000 or '\x00' in command:
            raise ValueError('命令无效')
        if type(timeout) is not int or not 1 <= timeout <= maximum:
            raise ValueError(f'超时应为 1～{maximum} 秒')
        directory = self.workspace.path(cwd)
        if not directory.is_dir():
            raise ValueError('工作目录不存在')
        return directory

    def start(self, command, cwd='', timeout=3600, description='', *, _completion=None):
        self._validate(command, cwd, timeout, 604800)
        if not isinstance(description, str) or len(description) > 1000:
            raise ValueError('任务描述最长 1000 字符')
        if len(self.tasks) >= 16:
            raise ValueError('最多同时运行 16 个后台任务')
        while len(self.jobs) >= 100:
            oldest = next((key for key, value in self.jobs.items() if value['status'] != 'running'
                and (not value.get('completion') or value.get('notified'))), None)
            if oldest is None:
                raise ValueError('后台任务记录等待通知，请稍后再启动')
            (self.job_dir / (oldest + '.json')).unlink(missing_ok=True)
            del self.jobs[oldest]
        record = dict(id=uuid.uuid4().hex, command=command, cwd=cwd, description=description,
            timeout=timeout, status='running', started_at=time.time(), finished_at=None,
            output='', output_bytes=0, truncated=False, exit_code=None, timed_out=False,
            completion=_completion, notified=False)
        self._save(record)
        self.jobs[record['id']] = record
        self.tasks[record['id']] = asyncio.create_task(self._execute(record))
        return self._view(record)

    @staticmethod
    def _view(record, output=True):
        return {key: value for key, value in record.items() if output or key != 'output'}

    def list_jobs(self):
        return [self._view(record, output=False) for record in reversed(list(self.jobs.values()))]

    def pending_notifications(self):
        return [self._view(record) for record in self.jobs.values() if record['status'] != 'running'
            and record.get('completion') and not record.get('notified')]

    def mark_notified(self, id):
        self.jobs[id]['notified'] = True
        self._save(self.jobs[id])

    async def job(self, id, wait_seconds=0):
        if type(wait_seconds) is not int or not 0 <= wait_seconds <= 30:
            raise ValueError('等待时间应为 0～30 秒')
        if id not in self.jobs:
            raise ValueError('后台任务不存在')
        task = self.tasks.get(id)
        if task and wait_seconds:
            await asyncio.wait({task}, timeout=wait_seconds)
        return self._view(self.jobs[id])

    async def cancel_job(self, id):
        if id not in self.jobs:
            raise ValueError('后台任务不存在')
        task = self.tasks.get(id)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            # Cancellation may arrive before _execute gets its first turn.
            if self.jobs[id]['status'] == 'running':
                self.jobs[id].update(status='cancelled', finished_at=time.time())
                self._save(self.jobs[id])
            self.tasks.pop(id, None)
        return self._view(self.jobs[id])

    async def _execute(self, record):
        last_saved = time.monotonic()

        def progress(result):
            nonlocal last_saved
            record.update(result)
            if time.monotonic() - last_saved >= 1:
                self._save(record)
                last_saved = time.monotonic()

        try:
            result = await self.run(record['command'], record['cwd'], record['timeout'],
                _progress=progress, _maximum=604800)
            record.update(result, status='timed_out' if result['timed_out'] else
                ('completed' if result['exit_code'] == 0 else 'failed'))
        except asyncio.CancelledError:
            record['status'] = 'cancelled'
        except Exception as exc:
            record.update(status='failed', error=str(exc))
        finally:
            record['finished_at'] = time.time()
            self.tasks.pop(record['id'], None)
            self._save(record)

    @staticmethod
    def kill(process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    async def stop(self):
        await asyncio.gather(*(self.cancel_job(id) for id in list(self.tasks)), return_exceptions=True)
        processes = list(self.processes)
        for process in processes:
            self.kill(process)
        await asyncio.gather(*(process.wait() for process in processes), return_exceptions=True)

    async def run(self, command, cwd='', timeout=60, *, _progress=None, _maximum=600):
        directory = self._validate(command, cwd, timeout, _maximum)
        started = time.monotonic()
        creation = asyncio.create_task(asyncio.create_subprocess_exec('/bin/sh', '-c', command,
            cwd=directory, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT, start_new_session=True))
        try:
            process = await asyncio.shield(creation)
        except asyncio.CancelledError:
            process = await creation
            self.kill(process)
            await process.communicate()
            raise
        self.processes.add(process)
        head, tail, total = bytearray(), bytearray(), 0

        def snapshot():
            output = head.decode('utf-8', errors='replace')
            if total > 65536:
                output += '\n…输出已截断…\n'
            output += tail.decode('utf-8', errors='replace')
            return dict(output=output, output_bytes=total, truncated=total > 65536)

        async def drain():
            nonlocal total
            while True:
                chunk = await process.stdout.read(8192)
                if not chunk:
                    break
                total += len(chunk)
                take = min(len(chunk), 49152 - len(head))
                head.extend(chunk[:take])
                tail.extend(chunk[take:])
                if len(tail) > 16384:
                    del tail[:-16384]
                if _progress:
                    _progress(snapshot())

        reader = asyncio.create_task(drain())
        timed_out = False

        async def cleanup():
            # A command invocation owns its process group, including background children.
            self.kill(process)
            await process.wait()
            try:
                await asyncio.wait_for(asyncio.shield(reader), 2)
            except (TimeoutError, asyncio.CancelledError):
                reader.cancel()
                await asyncio.gather(reader, return_exceptions=True)
            finally:
                self.processes.discard(process)

        try:
            async with asyncio.timeout(timeout):
                await process.wait()
                await asyncio.shield(reader)
        except TimeoutError:
            timed_out = True
        finally:
            job = asyncio.create_task(cleanup())
            try:
                await asyncio.shield(job)
            except asyncio.CancelledError:
                await job
                raise
        if _progress:
            _progress(snapshot())
        return {'exit_code': process.returncode, 'timed_out': timed_out, **snapshot(),
            'cwd': directory.relative_to(self.workspace.root).as_posix(),
            'duration_ms': round((time.monotonic() - started) * 1000)}
