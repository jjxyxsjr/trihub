"""trihub 公开体检页 —— 输入三平台用户名，出只读对账报告。免 token、零写操作。"""
import os
# 创空间机房在国内：HF 走 hf-mirror（huggingface_hub 自动读 HF_ENDPOINT）
if os.environ.get("TRIHUB_PROXY", "0") != "1":
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
# 本地 Mac 测 HF 需 TRIHUB_PROXY=1（走 Clash 7897）；创空间直连
os.environ.setdefault("USE_PROXY", os.environ.get("TRIHUB_PROXY", "0"))
import gradio as gr
from trihub.audit import audit


def run(gh, hf, ms):
    gh, hf, ms = gh.strip(), hf.strip(), ms.strip()
    try:
        data, by_name, cov, findings = audit(gh or "_", hf or "_", ms or "_")
    except Exception as e:
        return f"# 体检失败\n\n```\n{e}\n```", [], [], []
    n_gh, n_hf, n_ms = len(data["github"]), len(data["hf"]), len(data["ms"])
    gh_note = "" if n_gh else "（GitHub 在本机/机房不可达，已降级跳过）"

    md = [f"## 📊 资产总览\n",
          f"| 平台 | 仓库数 |\n|---|---|\n",
          f"| GitHub `{gh}` | {n_gh} {gh_note} |\n",
          f"| Hugging Face `{hf}` | {n_hf} |\n",
          f"| ModelScope `{ms}` | {n_ms} |\n"]
    md.append(f"\n**HF∩MS 同名覆盖：{len(cov['all'])} 个** · "
              f"**只在魔搭未镜像 HF：{len(cov['ms_no_hf'])} 个**\n")

    # 覆盖表
    cover = []
    for k in cov["all"]:
        plats = by_name[k]
        cover.append([k,
                      "✓" if "hf" in plats else "",
                      "✓" if "ms" in plats else "",
                      "✓" if "github" in plats else ""])
    # 缺口表
    gap = [[r["full"], r.get("desc", "")[:40]] for _, r in cov["ms_no_hf"]]
    # 问题表
    seen, issues = set(), []
    for kind, plat, full, detail in findings:
        sig = (kind, full, str(detail))
        if sig in seen:
            continue
        seen.add(sig)
        icon = {"card_missing": "🪪 缺卡面字段", "no_xlink": "🔗 缺跨平台链",
                "broken_link": "💔 残链"}.get(kind, kind)
        issues.append([plat, full, icon, str(detail)])

    return ("".join(md),
            cover if cover else [["（无同名覆盖）", "", "", ""]],
            (issues if issues else [["✓", "未发现问题", "", ""]]),
            gap if gap else [["（全部已镜像）", ""]])


with gr.Blocks(title="trihub · 三平台作品位体检") as demo:
    gr.Markdown("# 🧭 trihub · AI 作品位三平台体检\n"
                "输入你在 GitHub / Hugging Face / ModelScope 的用户名，一键对账：**镜像覆盖缺口、"
                "模型卡要素、跨平台链接、残链**。全程只读，不需要任何 token。")
    with gr.Row():
        gh = gr.Textbox(label="GitHub", value="jjxyxsjr", scale=1)
        hf = gr.Textbox(label="Hugging Face", value="jjshin", scale=1)
        ms = gr.Textbox(label="ModelScope", value="theGAI", scale=1)
    btn = gr.Button("开始体检", variant="prototype" if False else "primary")
    summary = gr.Markdown()
    with gr.Tab("同名覆盖（HF/MS/GH）"):
        cover_tbl = gr.Dataframe(headers=["模型", "HF", "MS", "GH"],
                                 datatype=["str", "str", "str", "str"], wrap=True)
    with gr.Tab(f"问题清单"):
        issue_tbl = gr.Dataframe(headers=["平台", "仓库", "问题", "详情"],
                                 datatype=["str", "str", "str", "str"], wrap=True)
    with gr.Tab("镜像缺口（只在魔搭）"):
        gap_tbl = gr.Dataframe(headers=["魔搭仓库", "说明"], datatype=["str", "str"], wrap=True)
    gr.Markdown("<center>Powered by <a href='https://github.com/jjxyxsjr/trihub' target='_blank'>"
                "trihub</a> · GitHub/HF/ModelScope portfolio auditor · 只读 · 零追踪</center>")
    btn.click(run, [gh, hf, ms], [summary, cover_tbl, issue_tbl, gap_tbl])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(__import__("os").environ.get("SERVER_PORT", "7860")), theme=gr.themes.Soft())
