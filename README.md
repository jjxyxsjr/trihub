# trihub — 三平台作品位对账与操控

一个地方看清并操控你的 **GitHub / Hugging Face / ModelScope** 作品位。

市面上只有单平台工具（`hf` CLI、modelscope SDK、gh），没有跨三平台的发布/对账层——
同一个微调模型往往三平台都要发，卡面要素、跨平台链接、镜像覆盖靠人肉记，漏了没人提醒。

## v0.1 — 只读对账（当前）

```bash
uv run python -m trihub --gh jjxyxsjr --hf jjshin --ms theGAI
```

报告三件事：
- **同名覆盖**：HF∩MS 哪些模型已对齐，哪些只在一边（镜像缺口）
- **卡面要素**：HF 模型卡缺 license / base_model / pipeline_tag / library_name
- **跨平台链**：双向回链缺失、残链（如指向合集根目录的假链接）

首次实战即抓出真实缺口：GRPO 卡缺 pipeline_tag（已修）。

## 路线

- v0.1 只读对账 ✅
- v0.2 操控 ✅（2026-10-12 真机全验）
  - `trihub audit` 对账报告
  - `trihub fix-card <hf_repo> --fields '{"pipeline_tag":"text-generation"}' [--yes]` 补卡面字段
  - `trihub link --ms theGAI/X --hf jjshin/X [--yes]` 跨平台回链（幂等）
  - `trihub publish theGAI/X [--private] [--yes]` 魔搭→HF 全量镜像（建仓+权重+卡搬运+source 标注）
  - 纪律：默认 dry-run、--yes 才写、写后内容级终证（写响应假阴性家族防御）
- v0.3 发布：一个模型三平台镜像 + 卡面双语适配
- MCP 层：把 trihub 暴露给 agent（ms-hub-insight 的三平台升级版）
- 公开只读体检页（创空间，输入用户名出报告，免 token）

## 设计原则

小而精：不做平台客户端复刻，只做三平台之间那条没人管的缝。
只读先行、写操作 dry-run、所有断言内容级终证（三平台都有写响应假阴性家族）。

## MCP server（给 agent 用）

```bash
# stdio JSON-RPC，不依赖 mcp SDK；配置到你的 agent：
uv run --with git+https://github.com/jjxyxsjr/trihub python -m trihub.mcp_server
```

| 工具 | 读写 | 作用 |
|---|---|---|
| `portfolio_audit` | 只读 | 三平台对账（覆盖/缺口/卡面/链接/残链） |
| `list_repos` | 只读 | 列某平台某用户的仓库 + 卡面字段/链接 |
| `check_repo` | 只读 | 单仓体检 |
| `operate` | 写 | `fix_card` / `link` / `publish`；`execute=false` 默认只出计划，`true` 才落地并自动终证 |

## 公开体检页（创空间）

`studio/` 是自包含 Gradio 应用（免 token 只读体检），国内机房 HF 自动走 hf-mirror。
部署是魔搭网页专属环节（一键部署 API 建的空间不初始化 git 实体，配方见 `studio/HOW_TO_DEPLOY.md`）。

## 鉴权

只读全免 token。写操作读本机 `~/.cache/huggingface/token`（HF）、`~/.modelscope/token`（魔搭）；
GitHub 用 `GITHUB_TOKEN` 或本机 `gh` 登录态（无则匿名，只读限流降级）。
