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
- v0.2 一键补齐：跨平台链接、缺失卡面字段（写操作，dry-run 默认开）
- v0.3 发布：一个模型三平台镜像 + 卡面双语适配
- MCP 层：把 trihub 暴露给 agent（ms-hub-insight 的三平台升级版）
- 公开只读体检页（创空间，输入用户名出报告，免 token）

## 设计原则

小而精：不做平台客户端复刻，只做三平台之间那条没人管的缝。
只读先行、写操作 dry-run、所有断言内容级终证（三平台都有写响应假阴性家族）。
