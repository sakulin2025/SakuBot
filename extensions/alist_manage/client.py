"""AList API boundary. Every file operation is checked against first-level rules."""
import posixpath
from urllib.parse import quote, unquote, urlsplit

import requests


class PluginError(ValueError):
    pass


def normalize(path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise PluginError("请使用以 / 开头的 AList 路径")
    decoded = path
    for _ in range(4):
        new = unquote(decoded)
        if new == decoded:
            break
        decoded = new
    for value in (path, decoded):
        if "\\" in value or any(ord(c) < 32 for c in value):
            raise PluginError("路径包含非法字符")
        if any(part in (".", "..") for part in value.split("/")):
            raise PluginError("路径不能包含 . 或 ..")
    if decoded.count("/") != path.count("/"):
        raise PluginError("路径不能包含编码后的分隔符")
    return "/" + "/".join(p for p in path.split("/") if p)


def http_url(value):
    parsed = urlsplit(str(value))
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise PluginError("地址必须是 http/https URL，凭据请填写到独立配置项")
    return str(value).rstrip("/")


class AList:
    def __init__(self, config):
        self.config = config
        self.token = ""

    def rule(self, path, permission=None):
        path = normalize(path)
        if path == "/":
            raise PluginError("根目录只允许列出可见目录")
        root = "/" + path.split("/")[1]
        matches = [r for r in self.config.get("folder_rules", []) if normalize(r.get("path", "")) == root]
        if len(matches) != 1 or matches[0].get("ignore", True) is not False:
            raise PluginError("该目录被忽略或尚未配置权限")
        rule = matches[0]
        if permission and rule.get(permission) is not True:
            raise PluginError(f"该目录未开放 {permission} 权限")
        return rule

    def request(self, method, path, **kwargs):
        base = http_url(self.config.get("base_url", ""))
        timeout = max(1, min(int(self.config.get("timeout", 30)), 300))
        if not self.token:
            self.token = str(self.config.get("token") or "").strip()
            if not self.token:
                if not self.config.get("username") or not self.config.get("password"):
                    raise PluginError("请先在插件页面填写 token 或用户名和密码")
                result = self._send("POST", base + "/api/auth/login", timeout,
                                    json={"username": self.config["username"], "password": self.config["password"]})
                self.token = (result or {}).get("token", "")
                if not self.token:
                    raise PluginError("AList 登录未返回 token")
        headers = {"Authorization": self.token, **kwargs.pop("headers", {})}
        return self._send(method, base + path, timeout, headers=headers, **kwargs)

    @staticmethod
    def _send(method, url, timeout, **kwargs):
        try:
            response = requests.request(method, url, timeout=timeout, allow_redirects=False, **kwargs)
            if response.status_code != 200:
                raise PluginError(f"AList 请求失败（HTTP {response.status_code}）")
            body = response.json()
            if body.get("code") != 200:
                # Upstream messages can contain credentials, driver paths, or URLs.
                raise PluginError(f"AList 拒绝请求（API {body.get('code')}）")
            return body.get("data")
        except (requests.RequestException, ValueError) as exc:
            if isinstance(exc, PluginError):
                raise
            raise PluginError("AList 连接失败或响应格式错误") from None

    def raw_list(self, path, page=1):
        return self.request("POST", "/api/fs/list", json={
            "path": path, "password": self.config.get("path_password", ""),
            "page": page, "per_page": 200, "refresh": False,
        }) or {}

    @staticmethod
    def metadata(item):
        return {k: item.get(k) for k in ("name", "size", "is_dir", "modified")}

    def listing(self, path, page=1):
        path = normalize(path)
        if path != "/":
            self.rule(path)
        data = self.raw_list(path, max(1, int(page)))
        rows = []
        for item in data.get("content") or []:
            child = normalize(posixpath.join(path, item["name"]))
            try:
                rule = self.rule(child)
            except PluginError:
                continue
            if path == "/" and not item.get("is_dir"):
                continue
            rows.append({**self.metadata(item), "path": child,
                         "permissions": {k: rule.get(k, False) for k in ("download", "add", "delete")}})
        # Never forward sign, raw_url, thumbnails, readme or headers during browsing.
        return {"path": path, "page": page, "items": rows, "page_size": 200}

    def info(self, path, download=False):
        path = normalize(path)
        self.rule(path, "download" if download else None)
        item = self.request("POST", "/api/fs/get", json={"path": path, "password": self.config.get("path_password", "")}) or {}
        result = self.metadata(item)
        if download:
            if item.get("is_dir"):
                raise PluginError("请列出目录后逐个下载文件")
            public = self.config.get("public_url") or self.config.get("base_url")
            url = http_url(public) + "/d" + quote(path, safe="/")
            if item.get("sign"):
                url += "?sign=" + quote(item["sign"], safe="")
            result["download_url"] = url
        return result

    def check_write(self, action, path, target=""):
        path = normalize(path)
        if len(path.strip("/").split("/")) < 2:
            raise PluginError("不能修改第一层目录本身；请操作目录内的文件或子目录")
        if action in ("mkdir", "upload"):
            self.rule(path, "add")
        elif action == "remove":
            self.rule(path, "delete")
        elif action in ("rename", "move", "copy"):
            self.rule(path, "download" if action == "copy" else "delete")
            if action == "rename":
                self.rule(path, "add")
                if not target or target in (".", "..") or "/" in target or "\\" in target:
                    raise PluginError("重命名目标必须是单个文件名")
                normalize(posixpath.join(posixpath.dirname(path), target))
            else:
                target = normalize(target)
                self.rule(target, "add")
                if target == "/" or target == path or target.startswith(path + "/"):
                    raise PluginError("不能移动或复制到根目录、自身或自己的子目录")
        else:
            raise PluginError("未知写操作")
        return path, target

    def ensure_absent(self, path):
        parent, name = posixpath.split(path)
        page = 1
        while True:
            data = self.raw_list(parent, page)
            rows = data.get("content") or []
            if any(item.get("name") == name for item in rows):
                raise PluginError("目标已存在。为隔离添加与删除权限，插件不允许覆盖，请先单独删除")
            if len(rows) < 200 or page * 200 >= int(data.get("total", page * 200 + 1)):
                return
            page += 1

    def write(self, action, path, target="", source_url=""):
        path, target = self.check_write(action, path, target)
        parent, name = posixpath.split(path)
        if action == "mkdir":
            self.ensure_absent(path)
            self.request("POST", "/api/fs/mkdir", json={"path": path})
        elif action == "remove":
            self.request("POST", "/api/fs/remove", json={"dir": parent, "names": [name]})
        elif action == "rename":
            self.ensure_absent(posixpath.join(parent, target))
            self.request("POST", "/api/fs/rename", json={"path": path, "name": target})
        elif action in ("move", "copy"):
            self.ensure_absent(posixpath.join(target, name))
            self.request("POST", f"/api/fs/{action}", json={"src_dir": parent, "dst_dir": target, "names": [name]})
        elif action == "upload":
            self.ensure_absent(path)
            limit = max(1, min(int(self.config.get("max_upload_mb", 100)), 1024)) * 1024 * 1024
            try:
                with requests.get(http_url(source_url), stream=True, timeout=30) as response:
                    if response.status_code != 200:
                        raise PluginError(f"下载上传来源失败（HTTP {response.status_code}）")
                    content = bytearray()
                    for chunk in response.iter_content(65536):
                        content.extend(chunk)
                        if len(content) > limit:
                            raise PluginError("上传来源超过插件的体积限制")
                self.request("PUT", "/api/fs/put", data=bytes(content), headers={
                    "File-Path": quote(path, safe=""), "Content-Type": "application/octet-stream",
                    "Content-Length": str(len(content)), "As-Task": "false",
                })
            except requests.RequestException:
                raise PluginError("读取上传来源失败") from None
        return {"success": True, "action": action, "path": path, "target": target}

    def discover(self):
        """Admin-only caller: preserve rules and add new root folders as ignored."""
        existing = {normalize(r["path"]): r for r in self.config.get("folder_rules", [])}
        page = 1
        while True:
            data = self.raw_list("/", page)
            rows = data.get("content") or []
            for item in rows:
                if item.get("is_dir"):
                    path = normalize("/" + item["name"])
                    existing.setdefault(path, {"__template_key": "folder", "path": path, "ignore": True,
                                               "download": False, "add": False, "delete": False})
            if len(rows) < 200 or page * 200 >= int(data.get("total", page * 200 + 1)):
                break
            page += 1
        return list(existing.values())
