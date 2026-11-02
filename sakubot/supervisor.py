"""Small parent process: authenticated local restart and graceful child shutdown."""
import asyncio
import contextlib
import json
import os
import secrets
import signal
import sys
import time
import uuid


async def supervise():
    secret = secrets.token_urlsafe(32)
    restart, stopping = asyncio.Event(), asyncio.Event()
    last_restart = 0.0
    restart_operation = ""

    async def receive(reader, writer):
        nonlocal last_restart, restart_operation
        try:
            async with asyncio.timeout(3):
                data = json.loads(await reader.readline())
                if not isinstance(data,dict): data={}
                allowed = secrets.compare_digest(str(data.get('secret', '')), secret)
                allowed = allowed and data.get('action') == 'restart' and not stopping.is_set()
                allowed = allowed and (not last_restart or time.monotonic() - last_restart > 30)
                if allowed:
                    last_restart = time.monotonic()
                    restart_operation = str(data.get("operation_id", ""))
                writer.write(json.dumps({'accepted': allowed}).encode() + b'\n')
                await writer.drain()
                if allowed:
                    restart.set()
        except (ValueError, TimeoutError, ConnectionError):
            pass
        finally:
            writer.close()
            with contextlib.suppress(ConnectionError):
                await writer.wait_closed()

    server = await asyncio.start_server(receive, '127.0.0.1', 0, limit=8192)
    env = {**os.environ, 'SAKUBOT_SUPERVISOR_PORT': str(server.sockets[0].getsockname()[1]),
           'SAKUBOT_SUPERVISOR_SECRET': secret}
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stopping.set))
    async with server:
        while not stopping.is_set():
            restart.clear()
            child = await asyncio.create_subprocess_exec(sys.executable, '-m', 'sakubot', '--worker',
                env={**env, 'SAKUBOT_BOOT_ID': uuid.uuid4().hex, 'SAKUBOT_RESTART_OPERATION': restart_operation})
            exited = asyncio.create_task(child.wait())
            requested = asyncio.create_task(restart.wait())
            terminated = asyncio.create_task(stopping.wait())
            await asyncio.wait((exited, requested, terminated), return_when=asyncio.FIRST_COMPLETED)
            should_restart = restart.is_set() and not stopping.is_set()
            if child.returncode is None:
                if os.name == 'nt':
                    child.terminate()
                else:
                    child.send_signal(signal.SIGTERM)
                try:
                    await asyncio.wait_for(asyncio.shield(exited), 45)
                except TimeoutError:
                    child.kill()
                    await exited
            for task in (exited, requested, terminated):
                if not task.done(): task.cancel()
            await asyncio.gather(exited, requested, terminated, return_exceptions=True)
            if not should_restart:
                return child.returncode if not stopping.is_set() else 0
            print('SakuBot supervisor: restarting worker', flush=True)
    return 0
