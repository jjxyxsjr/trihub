# 创空间部署（git-backed 创建是浏览器会话专属，文件推送全自动）

## 分工（2026-10-13 逆向终裁）
- **创建 Studio 必须网页**：Bearer POST /v1/studios 两种模式都只产生"僵死记录"（200 占名但无详情/无 git repo，4 次实证）；网页创建的空间有 "System init .gitattributes" commit + 可 clone。和合集/pin 同属浏览器会话专属
- **创建后文件推送全自动**：trihub studio-push 走 POST /v1/studios/file（multipart，Bearer 可用）

## 步骤
1. 用户网页：modelscope.cn/studios/create → SDK 选 Gradio → 名字（建议 trihub-auditor）→ 公开 → 创建（不要选模板/模型）
2. 一条命令推全部文件：
   uv run python -m trihub studio-push theGAI trihub-auditor studio --yes
3. 平台检测到 app.py 自动构建（免费 CPU 2vCPU/8G），repo/files 内容级终证

## 端点配方
- 文件写：POST /v1/studios/file，multipart 字段 owner/name/FilePath/Revision(master)/File(文件)/CommitMessage → {Data:{Uuid}}
- 文件读：GET /v1/studio/{owner}/{name}/repo/files?Revision=master
- 详情：GET /v1/studio/{owner}/{name}
- git clone：https://oauth2:<MS_TOKEN>@www.modelscope.cn/studios/owner/name.git（仅网页建的空间可 clone）
- 删除：DELETE /v1/dolphin/studio/query {Path,Name}（异步，名字软占用）
