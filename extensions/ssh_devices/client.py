"""SSH device records and independently managed persistent connections."""
import asyncio
import base64
import contextlib
import hashlib
import json
import os
import ntpath
import posixpath
import shlex
import stat
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import asyncssh


class PluginError(ValueError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PluginError(f"无法读取 {path.name}，请恢复该数据文件；不会自动清空已有记录。") from None


def write_json(path, value):
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


def seconds(value, maximum=86400):
    if isinstance(value, bool):
        raise PluginError("超时必须是秒数，0 表示不限制。")
    try:
        parsed = int(value)
    except (ValueError, TypeError, OverflowError):
        raise PluginError("超时必须是秒数，0 表示不限制。") from None
    if parsed < 0 or parsed > maximum or parsed != float(value):
        raise PluginError(f"超时必须为 0 到 {maximum} 之间的整数秒。")
    return parsed


class FirstConnection(asyncssh.SSHClient):
    def validate_host_public_key(self, host, addr, port, key):
        return True


@dataclass
class Connection:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    ssh: object = None
    shell: object = None
    sftp: object = None
    signature: str = ""
    home: str = ""
    cwd: str = ""
    platform: str = ""
    last_used: float = field(default_factory=time.monotonic)


class SSHDevices:
    OUTPUT_LIMIT = 16000
    FILE_LIMIT = 10 * 1024 * 1024

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.data_dir.chmod(0o700)
        self.state_path = self.data_dir / "state.json"
        self.pins_path = self.data_dir / "host_keys.json"
        self.state = read_json(self.state_path, {"devices": {}, "sessions": {}})
        self.pins = read_json(self.pins_path, {})
        if (not isinstance(self.state, dict) or not isinstance(self.state.get("devices"), dict)
                or not isinstance(self.state.get("sessions"), dict) or not isinstance(self.pins, dict)):
            raise PluginError("SSH 数据文件格式不正确，请恢复备份。")
        self.devices = self.state["devices"]
        self.sessions = self.state["sessions"]
        self.connections = {}
        self.pin_locks = {}
        self.key = self.load_key()

    def save(self):
        write_json(self.state_path, self.state)

    def load_key(self):
        path = self.data_dir / "id_ed25519"
        if path.exists():
            try:
                key = asyncssh.read_private_key(path)
                path.chmod(0o600)
                return key
            except (asyncssh.KeyImportError, OSError, ValueError):
                raise PluginError("插件私钥文件无法读取，请恢复 id_ed25519；不会自动替换已有密钥。") from None
        key = asyncssh.generate_private_key("ssh-ed25519")
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return self.load_key()
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(key.export_private_key())
        return key

    def public_key(self):
        public = self.key.export_public_key().decode().strip()
        quoted = shlex.quote(public)
        command = ('mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh" && '
                   'touch "$HOME/.ssh/authorized_keys" && chmod 600 "$HOME/.ssh/authorized_keys" && '
                   '(grep -qxF -- ' + quoted + ' "$HOME/.ssh/authorized_keys" || '
                   "printf '\\n%s\\n' " + quoted + ' >> "$HOME/.ssh/authorized_keys")')
        return {"public_key": public, "fingerprint": self.key.get_fingerprint(), "trust_command": command,
                "next": "给用户公钥和可选信任命令，再收集设备名字、描述、地址和用户名；不要主动询问端口，未提供时使用22。"}

    @staticmethod
    def find(records, reference, label, field_name):
        if not isinstance(reference, str):
            raise PluginError(f"请使用{label} ID 或名字。")
        if reference in records:
            return records[reference]
        matches = [item for item in records.values() if item[field_name].casefold() == reference.strip().casefold()]
        if len(matches) == 1:
            return matches[0]
        raise PluginError(f"{label}不存在或名称不唯一，请先列出记录并使用对应 ID。")

    def device(self, reference):
        return self.find(self.devices, reference, "设备", "name")

    def session(self, reference):
        return self.find(self.sessions, reference, "会话", "description")

    def connection(self, record):
        return self.connections.setdefault(record["id"], Connection(cwd=record.get("cwd", "")))

    async def device_action(self, action, reference="", details=None):
        details = {} if details is None else details
        if not isinstance(details, dict):
            raise PluginError("details 必须是包含设备字段的对象。")
        if action == "list":
            return {"devices": list(self.devices.values())}
        if action == "get":
            return dict(self.device(reference))
        if action == "remove":
            record = self.device(reference)
            affected = [s["id"] for s in self.sessions.values() if s["device_id"] == record["id"]]
            closing = []
            for session_id in affected:
                self.sessions.pop(session_id, None)
                connection = self.connections.pop(session_id, None)
                if connection:
                    closing.append(connection)
            self.devices.pop(record["id"])
            self.save()
            await asyncio.gather(*(self.close(c) for c in closing))
            return {"removed": record["id"], "name": record["name"]}
        if action not in ("add", "update"):
            raise PluginError("设备 action 只能是 list/get/add/update/remove。")
        allowed = {"name", "description", "address", "username", "port"}
        if set(details) - allowed:
            raise PluginError("设备字段只支持 name、description、address、username、port。")
        old = dict(self.device(reference)) if action == "update" else None
        record = {**(old or {"id": uuid.uuid4().hex[:12], "port": 22, "created_at": timestamp()}), **details}
        for name in ("name", "description", "address", "username"):
            value = record.get(name)
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise PluginError(f"请提供设备的 {name}；端口未说明时直接使用22。")
            record[name] = value.strip()
        if any(d["id"] != record["id"] and d["name"].casefold() == record["name"].casefold() for d in self.devices.values()):
            raise PluginError("设备名字已存在，请使用 update 修改原设备，或选择另一个名字。")
        port = seconds(record.get("port", 22), 65535)
        if not port:
            raise PluginError("端口必须在 1 到 65535 之间。")
        record.update(port=port, updated_at=timestamp())
        changed = old and any(old[k] != record[k] for k in ("address", "username", "port"))
        self.devices[record["id"]] = record
        closing = []
        if changed:
            for session in self.sessions.values():
                if session["device_id"] == record["id"]:
                    session["cwd"] = ""
                    connection = self.connection(session)
                    connection.cwd = ""
                    closing.append(connection)
        self.save()
        await asyncio.gather(*(self.close(c) for c in closing))
        return {"saved": True, "device": dict(record), "connected": False}

    @staticmethod
    async def close(connection):
        shell, ssh = connection.shell, connection.ssh
        connection.ssh = connection.shell = connection.sftp = None
        connection.home = ""
        connection.platform = ""
        if shell:
            shell.close()
        if ssh:
            ssh.close()
            with contextlib.suppress(asyncssh.Error, OSError, asyncio.TimeoutError):
                await asyncio.wait_for(ssh.wait_closed(), 5)

    async def terminate(self):
        await asyncio.gather(*(self.close(c) for c in list(self.connections.values())))

    async def reap_idle(self):
        while True:
            await asyncio.sleep(15)
            for record in list(self.sessions.values()):
                connection = self.connections.get(record["id"])
                idle = record["idle_timeout"]
                if connection and idle and not connection.lock.locked() and time.monotonic() - connection.last_used >= idle:
                    async with connection.lock:
                        await self.close(connection)

    def touch(self, record, connection):
        connection.last_used = time.monotonic()
        device = self.devices.get(record["device_id"])
        if self.sessions.get(record["id"]) is not record or device is None:
            return
        signature = hashlib.sha256(json.dumps([device["address"], device["port"], device["username"]]).encode()).hexdigest()
        if connection.signature != signature:
            return
        record.update(cwd=connection.cwd, last_used_at=timestamp())
        self.save()

    def info(self, record):
        connection = self.connections.get(record["id"])
        device = self.devices.get(record["device_id"], {"name": "已移除设备", "address": "", "username": "", "port": 0})
        return {**record, "device": device["name"], "address": device["address"],
                "username": device["username"], "port": device["port"],
                "shell": ("powershell" if connection.platform == "windows" else "posix") if connection and connection.platform else "not_detected",
                "connected": bool(connection and connection.ssh and not connection.ssh.is_closed()),
                "busy": bool(connection and connection.lock.locked())}

    async def session_action(self, action, device="", session_id="", details=None):
        details = {} if details is None else details
        if not isinstance(details, dict) or set(details) - {"description", "timeout", "idle_timeout"}:
            raise PluginError("会话 details 只支持 description、timeout、idle_timeout。")
        if action == "list":
            device_id = self.device(device)["id"] if device else None
            return {"sessions": [self.info(s) for s in self.sessions.values() if not device_id or s["device_id"] == device_id]}
        if action == "open":
            target = self.device(device)
            record = {"id": uuid.uuid4().hex[:12], "device_id": target["id"],
                      "description": details.get("description") or target["name"] + "终端",
                      "timeout": seconds(details.get("timeout", 60)),
                      "idle_timeout": seconds(details.get("idle_timeout", 0), 604800),
                      "cwd": "", "created_at": timestamp(), "last_used_at": timestamp()}
            if not isinstance(record["description"], str):
                raise PluginError("会话描述必须是文本。")
            record["description"] = record["description"].strip() or target["name"] + "终端"
            self.sessions[record["id"]] = record
            connection = self.connection(record)
            try:
                async with connection.lock:
                    await self.connect(record, connection)
                    self.touch(record, connection)
            except BaseException:
                await self.close(connection)
                self.connections.pop(record["id"], None)
                self.sessions.pop(record["id"], None)
                self.save()
                raise
            return self.info(record)
        record = self.session(session_id)
        if action == "get":
            return self.info(record)
        connection = self.connection(record)
        if action in ("disconnect", "remove", "reset"):
            if action == "remove":
                self.sessions.pop(record["id"], None)
                self.connections.pop(record["id"], None)
                self.save()
                await self.close(connection)
                return {"removed": record["id"]}
            # Interrupt a running operation rather than waiting for its lock.
            await self.close(connection)
            if action == "reset":
                async with connection.lock:
                    record["cwd"] = connection.cwd = ""
            self.save()
            return self.info(record)
        async with connection.lock:
            if action == "connect":
                await self.connect(record, connection)
                self.touch(record, connection)
            elif action == "update":
                updated = dict(record)
                if "description" in details:
                    if not isinstance(details["description"], str) or not details["description"].strip():
                        raise PluginError("会话描述不能为空。")
                    updated["description"] = details["description"].strip()
                if "timeout" in details:
                    updated["timeout"] = seconds(details["timeout"])
                if "idle_timeout" in details:
                    updated["idle_timeout"] = seconds(details["idle_timeout"], 604800)
                record.update(updated)
                self.save()
            else:
                raise PluginError("会话 action 只能是 list/open/get/update/connect/disconnect/reset/remove。")
        return self.info(record)

    async def handshake(self, device, pinned):
        return await asyncssh.connect(
            device["address"], port=device["port"], username=device["username"],
            client_keys=[self.key], agent_path=None, password_auth=False, kbdint_auth=False,
            known_hosts=([asyncssh.import_public_key(pinned)], [], []) if pinned else b"",
            client_factory=asyncssh.SSHClient if pinned else FirstConnection,
            connect_timeout=10, keepalive_interval=30, keepalive_count_max=3)

    async def connect(self, record, connection):
        if record["id"] not in self.sessions:
            raise PluginError("该会话已删除，请重新建立连接。")
        device = dict(self.devices[record["device_id"]])
        target = json.dumps([device["address"], device["port"]])
        signature = hashlib.sha256(json.dumps([device["address"], device["port"], device["username"]]).encode()).hexdigest()
        idle = record["idle_timeout"]
        expired = idle and time.monotonic() - connection.last_used >= idle
        if connection.ssh and not connection.ssh.is_closed() and connection.signature == signature and not expired:
            return
        await self.close(connection)
        ssh = None
        if target not in self.pins:
            async with self.pin_locks.setdefault(target, asyncio.Lock()):
                if target not in self.pins:
                    ssh = await self.handshake(device, None)
                    self.pins[target] = ssh.get_server_host_key().export_public_key().decode().strip()
                    try:
                        write_json(self.pins_path, self.pins)
                    except BaseException:
                        self.pins.pop(target, None)
                        ssh.close()
                        await ssh.wait_closed()
                        raise
        if ssh is None:
            ssh = await self.handshake(device, self.pins[target])
        current_device = self.devices.get(record["device_id"])
        if record["id"] not in self.sessions or current_device is None or any(
                current_device[k] != device[k] for k in ("address", "username", "port")):
            ssh.close()
            await ssh.wait_closed()
            raise PluginError("连接期间设备或会话已被修改或移除，请重新选择设备建立连接。")
        connection.ssh, connection.signature = ssh, signature
        connection.cwd = record.get("cwd", "")
        connection.last_used = time.monotonic()

    async def detect_platform(self, connection):
        if not connection.platform:
            # Probe only a fixed, read-only command; never replay a user command.
            result = await asyncio.wait_for(connection.ssh.run(
                "cmd.exe /d /c ver", encoding="utf-8", errors="replace"), 10)
            connection.platform = ("windows" if result.exit_status == 0 and
                                   "windows" in result.stdout.casefold() else "posix")
        return connection.platform

    async def sftp(self, connection):
        if connection.sftp is None:
            client = None
            try:
                client = await connection.ssh.start_sftp_client()
                connection.home = await client.realpath(".")
            except (asyncssh.Error, OSError) as exc:
                if client:
                    client.exit()
                raise PluginError(
                    f"SFTP 初始化失败（{type(exc).__name__}）。这不代表 SSH 认证失败，也不能仅据此断定未启用 SFTP。"
                    "请检查服务端 Subsystem sftp、sftp-server.exe 路径及是否有启动脚本向协议标准输出打印文字。"
                    "终端功能可单独使用；可先通过 ssh_terminal 的只读命令检查配置，不要自动修改 SSH 服务配置。"
                ) from None
            connection.sftp = client
            if not connection.cwd:
                connection.cwd = connection.home
        return connection.sftp

    @staticmethod
    def remote_path(connection, path):
        path = path or "."
        if not isinstance(path, str) or "\x00" in path:
            raise PluginError("文件路径必须是不含空字符的文本。")
        if connection.platform == "windows" or ntpath.splitdrive(connection.home.lstrip("/"))[0]:
            path = path.replace("\\", "/")
            if path == "~" or path.startswith("~/"):
                path = connection.home + path[1:]
            if path.startswith("/") and len(path) > 3 and path[2] == ":":
                path = path[1:]
            base = (connection.cwd or connection.home).replace("\\", "/")
            if base.startswith("/") and len(base) > 3 and base[2] == ":":
                base = base[1:]
            return ntpath.normpath(ntpath.join(base, path)).replace("\\", "/")
        if path == "~":
            return connection.home
        if path.startswith("~/"):
            return posixpath.normpath(posixpath.join(connection.home, path[2:]))
        return posixpath.normpath(posixpath.join(connection.cwd or connection.home, path))

    async def execute(self, session_id, command, timeout=0):
        if not isinstance(command, str) or not command.strip() or "\x00" in command:
            raise PluginError("请输入不含空字符的终端命令。")
        record = self.session(session_id)
        connection = self.connection(record)
        async with connection.lock:
            await self.connect(record, connection)
            await self.detect_platform(connection)
            device_name = self.devices[record["device_id"]]["name"]
            if connection.shell is None or connection.shell.stdout.at_eof():
                if connection.platform == "windows":
                    # One persistent PowerShell per connection. Commands arrive as
                    # base64 lines, bypassing cmd quoting and supporting multiline input.
                    startup = (
                        "$OutputEncoding = [Console]::OutputEncoding = [Console]::InputEncoding = "
                        "[System.Text.UTF8Encoding]::new($false); "
                        "while ($null -ne ($__ssh_line = [Console]::ReadLine())) { "
                        "$__ssh_script = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($__ssh_line)); "
                        ". ([ScriptBlock]::Create($__ssh_script)) }"
                    )
                    encoded = base64.b64encode(startup.encode("utf-16-le")).decode("ascii")
                    launch = "powershell.exe -NoLogo -NoProfile -NonInteractive -OutputFormat Text -EncodedCommand " + encoded
                else:
                    launch = "exec /bin/sh 2>&1"
                connection.shell = await connection.ssh.create_process(
                    launch, stderr=asyncssh.STDOUT, encoding="utf-8", errors="replace")
                if connection.cwd:
                    if connection.platform == "windows":
                        restore = "try { Set-Location -LiteralPath '" + connection.cwd.replace("'", "''") + "' -ErrorAction Stop } catch { Set-Location $HOME }"
                        connection.shell.stdin.write(base64.b64encode(restore.encode("utf-8")).decode("ascii") + "\n")
                    else:
                        connection.shell.stdin.write("cd " + shlex.quote(connection.cwd) + ' 2>/dev/null || cd "$HOME" || exit\n')
            shell = connection.shell
            marker = "SSH_" + uuid.uuid4().hex
            begin, end = "\n" + marker + ":", "\n" + marker + "_END\n"
            output, length, truncated = [], 0, False

            def keep(text):
                nonlocal length, truncated
                available = max(0, self.OUTPUT_LIMIT - length)
                if available:
                    output.append(text[:available])
                length += min(available, len(text))
                truncated |= len(text) > available

            async def collect():
                pending = ""
                while True:
                    chunk = await shell.stdout.read(8192)
                    if not chunk:
                        keep(pending)
                        return None
                    pending += chunk.replace("\r", "") if connection.platform == "windows" else chunk
                    if begin in pending:
                        before, metadata = pending.split(begin, 1)
                        keep(before)
                        while end not in metadata:
                            chunk = await shell.stdout.read(8192)
                            if not chunk or len(metadata) > 32768:
                                raise PluginError("终端已结束，命令可能已执行，请先检查结果，不要自动重试。")
                            metadata += chunk.replace("\r", "") if connection.platform == "windows" else chunk
                        status, connection.cwd = metadata.split(end, 1)[0].split("\n", 1)
                        return int(status)
                    safe = max(0, len(pending) - len(begin))
                    keep(pending[:safe])
                    pending = pending[safe:]

            timed_out, exit_code = False, None
            duration = seconds(timeout) if timeout else record["timeout"]
            try:
                if connection.platform == "windows":
                    encoded_command = base64.b64encode(command.encode("utf-8")).decode("ascii")
                    script = (
                        "$global:LASTEXITCODE = 0; $__ssh_status = 0; "
                        "try { . ([ScriptBlock]::Create([Text.Encoding]::UTF8.GetString("
                        "[Convert]::FromBase64String('" + encoded_command + "')))) | Out-Default; "
                        "$__ssh_ok = $?; $__ssh_status = $global:LASTEXITCODE; "
                        "if (-not $__ssh_ok -and $__ssh_status -eq 0) { $__ssh_status = 1 } "
                        "} catch { $_ | Out-String | ForEach-Object { [Console]::Write($_) }; $__ssh_status = 1 }; "
                        "[Console]::Write(\"`n" + marker + ":$__ssh_status`n\"); "
                        "[Console]::Write((Get-Location).Path); "
                        "[Console]::Write(\"`n" + marker + "_END`n\")"
                    )
                    shell.stdin.write(base64.b64encode(script.encode("utf-8")).decode("ascii") + "\n")
                else:
                    shell.stdin.write("eval " + shlex.quote(command) + "\n"
                                  "__ssh_status=$?\n"
                                  "printf '\\n" + marker + ":%s\\n' \"$__ssh_status\"\n"
                                  "pwd -P\n"
                                  "printf '" + marker + "_END\\n'\n")
                await shell.stdin.drain()
                exit_code = await asyncio.wait_for(collect(), duration or None)
            except asyncio.TimeoutError:
                timed_out = True
            except BaseException:
                shell.close()
                connection.shell = None
                raise
            finally:
                self.touch(record, connection)
            if exit_code is None:
                shell.close()
                connection.shell = None
            result = {"session_id": record["id"], "device": device_name,
                      "output": "".join(output), "exit_code": exit_code, "cwd": connection.cwd,
                      "truncated": truncated, "timed_out": timed_out,
                      "shell": "powershell" if connection.platform == "windows" else "posix"}
            if exit_code is None:
                result["note"] = "终端已关闭；命令可能已执行或仍有后台进程，请先检查结果，不要自动重试。"
            return result

    async def files(self, session_id, action, path=".", content="", target="", local_path=None):
        actions = {"list", "stat", "read", "write", "mkdir", "rename", "remove", "download", "upload"}
        if action not in actions:
            raise PluginError("未知文件操作。")
        record = self.session(session_id)
        connection = self.connection(record)
        async with connection.lock:
            await self.connect(record, connection)
            try:
                result = await asyncio.wait_for(
                    self.file_operation(connection, action, path, content, target, local_path), record["timeout"] or None)
                return {"session_id": record["id"], **result}
            finally:
                self.touch(record, connection)

    async def file_operation(self, connection, action, path, content, target, local_path):
        sftp = await self.sftp(connection)
        path = self.remote_path(connection, path)
        if action == "list":
            items = []
            async for entry in sftp.scandir(path):
                if entry.filename in (".", ".."):
                    continue
                items.append({"name": entry.filename, "size": entry.attrs.size,
                              "directory": stat.S_ISDIR(entry.attrs.permissions or 0)})
                if len(items) >= 200:
                    return {"path": path, "items": items, "truncated": True}
            return {"path": path, "items": items, "truncated": False}
        if action == "stat":
            attrs = await sftp.stat(path)
            return {"path": path, "size": attrs.size, "mtime": attrs.mtime,
                    "directory": stat.S_ISDIR(attrs.permissions or 0), "permissions": attrs.permissions}
        if action in ("read", "download"):
            cap = self.OUTPUT_LIMIT if action == "read" else self.FILE_LIMIT
            async with sftp.open(path, "rb") as remote:
                data = await remote.read(cap + 1)
            if action == "read":
                if b"\x00" in data:
                    raise PluginError("请使用 download 下载二进制文件。")
                return {"path": path, "content": data[:cap].decode("utf-8", errors="replace"), "truncated": len(data) > cap}
            if len(data) > cap:
                raise PluginError("单文件传输上限为10MB。")
            await asyncio.to_thread(Path(local_path).write_bytes, data)
            return {"path": path, "bytes": len(data)}
        if action in ("write", "upload"):
            if action == "write":
                if not isinstance(content, str):
                    raise PluginError("write 的 content 必须是文本。")
                data = content.encode("utf-8")
            else:
                if Path(local_path).stat().st_size > self.FILE_LIMIT:
                    raise PluginError("单文件传输上限为10MB。")
                with Path(local_path).open("rb") as source:
                    data = source.read(self.FILE_LIMIT + 1)
            if len(data) > self.FILE_LIMIT:
                raise PluginError("单文件传输上限为10MB。")
            async with sftp.open(path, "wb") as remote:
                await remote.write(data)
            return {"path": path, "bytes": len(data)}
        if action == "mkdir":
            await sftp.makedirs(path, exist_ok=True)
        elif action == "rename":
            if not target:
                raise PluginError("rename 需要目标路径 target。")
            target = self.remote_path(connection, target)
            await sftp.rename(path, target)
        elif action == "remove":
            attrs = await sftp.lstat(path)
            if stat.S_ISDIR(attrs.permissions or 0):
                await sftp.rmdir(path)
            else:
                await sftp.remove(path)
        return {"success": True, "path": path, "target": target}
