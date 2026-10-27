import asyncio
import json
import time
import uuid

from sakubot.plugin import object_schema, text
from sakubot.store import encode


class Confirmations:
    def setup_confirmations(self):
        self.pending_confirmations = {}
        self.api("requests", self.page_requests)
        self.api("requests/resolve", self.page_resolve, methods=("POST",))
        self.tool("team_requests", "查看专业团队待答复的问题和操作确认，后续用户答复可按 request_id 对应。",
            object_schema({"status": {"type": "string", "enum": ["waiting", "answered", "all"]}}), self.request_list)
        self.tool("team_resolve", "答复团队成员的待确认请求并恢复其执行。能自行判断时直接答复；需要用户信息时先询问，收到答复后再调用。confirmation 的 approved=true 表示同意，false 表示拒绝；question 用 answer 回答。",
            object_schema({"request_id": text(), "answer": text(), "approved": {"type": "boolean"}}, ("request_id",)), self.resolve_request)

    def add_confirmation_tool(self, agent):
        agent.tool("team_wait_confirmation", "待确认：向主 Agent 提问或请求确认某项操作，暂停本次执行。主 Agent 可自行判断或询问用户；拿到答复后此函数才返回，继续当前任务，无需重新派发。",
            object_schema({"kind": {"type": "string", "enum": ["question", "confirmation"]},
                "question": text("待回答的问题或待确认操作"), "context": text("主 Agent 判断所需信息"),
                "options": {"type": "array", "items": {"type": "string"}, "maxItems": 20}}, ("kind", "question")), self.wait_confirmation)

    def request_records(self, status="waiting"):
        rows = self.runtime.store.rows("SELECT * FROM team_requests WHERE (?='all' OR status=?) ORDER BY created DESC LIMIT 200", (status, status))
        for row in rows:
            row["options"] = json.loads(row["options"])
            row["approved"] = bool(row["approved"]) if row["approved"] is not None else None
        return rows

    async def request_list(self, invocation, args):
        return self.request_records(args.get("status", "waiting"))

    async def page_requests(self, request):
        return self.request_records("all")

    async def page_resolve(self, request):
        return await self.call_tool("team_resolve", await request.json())

    async def resolve_request(self, invocation, args):
        identifier = args["request_id"]
        row = self.runtime.store.one("SELECT * FROM team_requests WHERE id=?", (identifier,))
        if not row:
            raise ValueError("请求不存在")
        if row["status"] == "answered":
            return {"request_id": identifier, "status": "answered", "answer": row["answer"],
                "approved": bool(row["approved"]) if row["approved"] is not None else None}
        future = self.pending_confirmations.get(identifier)
        if row["status"] != "waiting" or future is None or future.done():
            raise ValueError("该请求已结束")
        answer, approved = args.get("answer", "").strip(), args.get("approved")
        if row["kind"] == "confirmation" and type(approved) is not bool:
            raise ValueError("请提供 approved")
        if row["kind"] == "question" and not answer:
            raise ValueError("请提供 answer")
        if not answer:
            answer = "同意" if approved else "拒绝"
        if len(answer) > 20000:
            raise ValueError("答复过长")
        result = {"request_id": identifier, "kind": row["kind"], "answer": answer, "approved": approved}
        self.runtime.store.execute("UPDATE team_requests SET status='answered',answer=?,approved=?,resolved=? WHERE id=? AND status='waiting'",
            (answer, approved, time.time(), identifier))
        future.set_result(result)
        self.cancel_wake("team-request:" + identifier)
        self.runtime.store.log("info", self.id, "team.request.answered", run_id=row["run_id"], data={"request_id": identifier, "agent_id": row["agent_id"]})
        return {**result, "status": "answered"}

    async def wait_confirmation(self, invocation, args):
        if invocation.control is None:
            raise ValueError("Agent 当前没有可暂停的运行")
        question, context = args["question"].strip(), args.get("context", "")
        if not question or len(question) > 10000 or len(context) > 20000:
            raise ValueError("请求内容无效")
        identifier = uuid.uuid4().hex[:12]
        future = asyncio.get_running_loop().create_future()
        self.pending_confirmations[identifier] = future
        store = self.runtime.store
        store.execute("INSERT INTO team_requests(id,agent_id,task_id,run_id,kind,question,context,options,status,created) VALUES (?,?,?,?,?,?,?,?,'waiting',?)",
            (identifier, invocation.agent_id, invocation.task_id, invocation.run_id, args["kind"], question, context, encode(args.get("options", [])), time.time()))
        store.execute("UPDATE tasks SET status='waiting',data=json_set(data,'$.waiting_request',?),updated=? WHERE id=? AND status='running'",
            (identifier, time.time(), invocation.task_id))
        store.execute("UPDATE tool_calls SET status='waiting' WHERE run_id=? AND call_id=? AND status='running'", (invocation.run_id, invocation.call_id))
        payload = {"request_id": identifier, "agent_id": invocation.agent_id, "task_id": invocation.task_id,
            "kind": args["kind"], "question": question, "context": context, "options": args.get("options", [])}
        try:
            await self.emit("wake", "团队成员等待你的答复。可以根据已有信息直接判断；需要用户信息时先向主人提问。获得答复后调用 team_resolve，恢复对应成员；不要重复派发任务。\n" + encode(payload),
                target=self.runtime.main_target(), priority=80, uid="team-request:" + identifier,
                meta={"team_request_id": identifier})
            store.log("info", self.id, "team.request.waiting", run_id=invocation.run_id, data=payload)
            result = await self.get_agent(invocation.agent_id).wait_for(future, invocation=invocation)
            store.execute("UPDATE tasks SET status='running',data=json_remove(data,'$.waiting_request'),updated=? WHERE id=? AND status='waiting'", (time.time(), invocation.task_id))
            store.execute("UPDATE tool_calls SET status='running' WHERE run_id=? AND call_id=? AND status='waiting'", (invocation.run_id, invocation.call_id))
            return result
        finally:
            self.pending_confirmations.pop(identifier, None)
            if not future.done():
                future.cancel()
            store.execute("UPDATE team_requests SET status='cancelled',resolved=?,error='运行已结束' WHERE id=? AND status='waiting'", (time.time(), identifier))
            self.cancel_wake("team-request:" + identifier)

    async def agent_reset(self, event):
        rows = self.runtime.store.rows("SELECT id FROM tasks WHERE json_extract(data,'$.agent_id')=? AND status IN ('pending','running','waiting')", (event["agent_id"],))
        for row in rows:
            await self.manage(None, {"action": "cancel", "id": row["id"]})

    async def stop(self):
        for future in self.pending_confirmations.values():
            if not future.done():
                future.cancel()
        await super().stop()
