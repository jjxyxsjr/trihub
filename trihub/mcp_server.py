"""trihub MCP server — 把三平台对账/操控暴露给 agent。
只读工具常开；写操作走 operate(execute=False) 出计划，execute=True 才落地（agent 安全闸）。
"""
from __future__ import annotations
import json
from . import ops
from .audit import audit as run_audit
from .platforms import list_github, list_hf, list_ms


def _audit_json(gh, hf, ms):
    data, by_name, cov, findings = run_audit(gh, hf, ms)
    return {
        "counts": {p: len(rs) for p, rs in data.items()},
        "hf_ms_covered": [by_name[k].get("hf", by_name[k].get("ms"))["full"]
                          for k in cov["all"]],
        "ms_only_not_mirrored": [r["full"] for _, r in cov["ms_no_hf"]],
        "hf_only_models": [r["full"] for _, r in cov["hf_no_ms"]],
        "issues": [{"kind": k, "platform": p, "repo": f, "detail": d}
                   for k, p, f, d in findings],
    }


# ---- 工具定义 ----
TOOLS = [
    {"name": "portfolio_audit",
     "description": "只读：对账 GitHub/HF/ModelScope 三平台作品位——同名覆盖、镜像缺口、卡面要素缺失、跨平台链/残链。",
     "inputSchema": {"type": "object", "properties": {
         "gh": {"type": "string", "default": "jjxyxsjr"},
         "hf": {"type": "string", "default": "jjshin"},
         "ms": {"type": "string", "default": "theGAI"}}, "required": []}},
    {"name": "list_repos",
     "description": "只读：列某平台某用户的仓库（github/hf/ms），含卡面字段与跨平台链接。",
     "inputSchema": {"type": "object", "properties": {
         "platform": {"type": "string", "enum": ["github", "hf", "ms"]},
         "owner": {"type": "string"}}, "required": ["platform", "owner"]}},
    {"name": "check_repo",
     "description": "只读：单仓体检——frontmatter 卡面字段 + 三平台链接 + 残链。",
     "inputSchema": {"type": "object", "properties": {
         "platform": {"type": "string", "enum": ["github", "hf", "ms"]},
         "repo": {"type": "string", "description": "owner/name"}}, "required": ["platform", "repo"]}},
    {"name": "operate",
     "description": "操控：action=fix_card|link|publish。execute=false（默认）只返回计划；"
                    "execute=true 才真写（写后自动内容级终证）。HF 写需 ~/.cache/huggingface/token，MS 写需 ~/.modelscope/token。",
     "inputSchema": {"type": "object", "properties": {
         "action": {"type": "string", "enum": ["fix_card", "link", "publish"]},
         "execute": {"type": "boolean", "default": False},
         "hf_repo": {"type": "string"},
         "fields_json": {"type": "string", "description": "fix_card 用，如 {\"pipeline_tag\":\"text-generation\"}"},
         "ms_repo": {"type": "string", "description": "link/publish 用，theGAI/name"},
         "private": {"type": "boolean", "default": False}},
         "required": ["action"]}},
]


async def call_tool(name: str, args: dict) -> str:
    if name == "portfolio_audit":
        return json.dumps(_audit_json(args.get("gh", "jjxyxsjr"),
                                      args.get("hf", "jjshin"), args.get("ms", "theGAI")),
                          ensure_ascii=False, indent=1)
    if name == "list_repos":
        fn = {"github": list_github, "hf": list_hf, "ms": list_ms}[args["platform"]]
        rs = fn(args["owner"])
        slim = [{"full": r["full"], "url": r["url"], "desc": r.get("desc", ""),
                 "card_fields": r.get("card_fields", {}),
                 "links": {k: v for k, v in r["links"].items() if v}} for r in rs]
        return json.dumps(slim, ensure_ascii=False, indent=1)
    if name == "check_repo":
        plat, repo = args["platform"], args["repo"]
        owner, nm = repo.split("/", 1)
        fn = {"github": list_github, "hf": list_hf, "ms": list_ms}[plat]
        for r in fn(owner):
            if r["full"].lower() == repo.lower():
                return json.dumps({"full": r["full"], "card_fields": r["card_fields"],
                                   "links": r["links"]}, ensure_ascii=False, indent=1)
        return json.dumps({"error": "not found", "repo": repo})
    if name == "operate":
        action, execute = args["action"], args.get("execute", False)
        if action == "fix_card":
            r = ops.fix_card(args["hf_repo"], json.loads(args["fields_json"]), yes=execute)
        elif action == "link":
            r = ops.link_pair(args["ms_repo"], args["hf_repo"], yes=execute)
        elif action == "publish":
            r = ops.publish_ms_to_hf(args["ms_repo"], args.get("hf_name"),
                                     private=args.get("private", False), yes=execute)
        else:
            r = {"ok": False, "msg": "unknown action"}
        return json.dumps(r, ensure_ascii=False, indent=1)
    return json.dumps({"error": f"unknown tool {name}"})


def main_stdio():
    """最小 JSON-RPC over stdio（不依赖 mcp SDK，任何环境可跑）。"""
    import sys, asyncio
    async def loop():
        buf = ""
        for line in sys.stdin:
            buf += line
            if not line.strip():
                if not buf.strip():
                    continue
            # 按行 JSON-RPC（每行一个请求）
            req_line = line.strip()
            if not req_line:
                continue
            try:
                req = json.loads(req_line)
            except Exception:
                continue
            rid = req.get("id")
            method = req.get("method")
            if method == "initialize":
                out = {"jsonrpc": "2.0", "id": rid, "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "trihub", "version": "0.2.0"}}}
            elif method == "tools/list":
                out = {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
            elif method == "tools/call":
                p = req.get("params", {})
                try:
                    text = await call_tool(p.get("name"), p.get("arguments", {}))
                    out = {"jsonrpc": "2.0", "id": rid,
                           "result": {"content": [{"type": "text", "text": text}]}}
                except Exception as e:
                    out = {"jsonrpc": "2.0", "id": rid,
                           "result": {"content": [{"type": "text",
                                       "text": json.dumps({"ok": False, "error": str(e)})}],
                                     "isError": True}}
            elif method == "notifications/initialized":
                continue
            else:
                out = {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": method}}
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    asyncio.run(loop())


if __name__ == "__main__":
    main_stdio()
