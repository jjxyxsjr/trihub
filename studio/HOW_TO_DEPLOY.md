# 创空间部署（网页创建是平台网页专属环节，约 1 分钟）

本目录是自包含部署包（trihub/ 是主包副本，创空间 build 无需访问 GitHub）。

1. modelscope.cn → 创空间 → 创建：SDK 选 Gradio，名字 `trihub-portfolio-auditor`，公开
2. 进入空间 → 文件（或 git clone 空间地址，网页创建的空间有 git）
3. 上传/推送本目录全部内容：app.py、requirements.txt、README.md、trihub/
4. 保存即自动构建；免费 CPU 实例（2vCPU/8GB），本应用纯只读无需 GPU

## 一键部署 API（已逆向，但创建的空间无 git 实体，仅供批量/自动化研究）
POST /api/v1/studios，字段（逐个校验，全必填）：
Name / Path(theGAI/<name>) / ModelPath(任意 theGAI 模型,无模型也要填) /
Visibility:5 / IsPublic:1 / DeployedByUser:true(bool) /
InstanceTypeName:"platform/2v-cpu-8g-mem" / ResourceRegion:"cn-beijing" /
DiskSize:50 / InstanceNumber:1 / SdkName:"gradio" / ExpiredMinutes:480
免费实例清单：GET /api/v1/studios/free_instance
空间 git token：GET /api/v1/studios/token?Path=<owner/name>
删除：DELETE /api/v1/dolphin/studio/query {Path,Name}
