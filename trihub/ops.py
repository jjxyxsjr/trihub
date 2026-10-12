"""v0.2 写操作：fix-card / link / publish。
纪律：默认 dry-run，--yes 才写；写后强制内容级终证（三平台写响应都有假阴性家族）。
frontmatter 注入坑（实测）：正则第一组含闭合 ---，任何块必须插在 fm 内容与闭合标记之间。
"""
from __future__ import annotations
import re, os, tempfile, urllib.request
from .platforms import PROXIES


def _split_fm(text: str):
    """返回 (fm 内容[无边界], 正文)。frontmatter 必须在文件头。"""
    if not text.startswith("---\n"):
        return None, text
    idx = text.find("\n---\n")
    if idx < 0:
        return None, text
    return text[3:idx], text[idx + 5:]


def _http_read(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "trihub/0.2"})
    op = urllib.request.build_opener(urllib.request.ProxyHandler(PROXIES or {}))
    with op.open(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


# ============ HF 基础件 ============
def _hf():
    from huggingface_hub import HfApi
    return HfApi()


def _hf_readme(rid: str) -> str:
    from huggingface_hub import hf_hub_download
    p = hf_hub_download(rid, "README.md", repo_type="model", force_download=True)
    return open(p, encoding="utf-8").read()


def _verify_hf(rid: str, needle: str) -> bool:
    return needle in _hf_readme(rid)


# ============ 1. fix-card：补 HF 卡 frontmatter 字段 ============
SCALARS = {"license", "pipeline_tag", "library_name", "language"}  # language 走数组
ARRAYS = {"language", "tags", "base_model"}


def fix_card(rid: str, fields: dict, yes: bool = False):
    """fields: {"pipeline_tag": "text-generation", "tags": ["a","b"], ...}"""
    txt = _hf_readme(rid)
    fm, body = _split_fm(txt)
    if fm is None:
        return {"ok": False, "msg": "no frontmatter"}
    changes = {}
    new_fm = fm.rstrip("\n")
    for k, v in fields.items():
        if re.search(rf"^{k}:", new_fm, re.M):
            changes[k] = "already-present"
            continue
        if k in ARRAYS and isinstance(v, (list, tuple)):
            block = k + ":\n" + "".join(f"- {x}\n" for x in v)
        else:
            block = f"{k}: {v}"
        new_fm += "\n" + block
        changes[k] = "added"
    if all(v == "already-present" for v in changes.values()):
        return {"ok": True, "msg": "nothing to do", "changes": changes}
    new_text = "---\n" + new_fm + "\n---\n" + body
    if not yes:
        return {"ok": True, "dry_run": True, "changes": changes, "preview": new_fm[-400:]}
    tmp = os.path.join(tempfile.gettempdir(), "trihub-fix-card.md")
    open(tmp, "w").write(new_text)
    _hf().upload_file(path_or_fileobj=tmp, path_in_repo="README.md", repo_id=rid,
                      repo_type="model", commit_message="trihub fix-card: " + ", ".join(
                          f"{k}={changes[k]}" for k in changes))
    # 内容级终证
    needle = [f"{k}:" for k, v in changes.items() if v == "added"]
    ok = all(_verify_hf(rid, n) for n in needle)
    return {"ok": ok, "verified": ok, "changes": changes}


# ============ 2. link：跨平台回链补齐 ============
def link_pair(ms_repo: str, hf_repo: str, yes: bool = False):
    """给 HF 卡补 MS 全量卡回链（Receipts 区），给 MS 卡补 HF 链（首个 ## 前）。幂等。"""
    actions = {}
    ms_name = ms_repo.split("/", 1)[1]
    # --- HF 侧 ---
    hf_txt = _hf_readme(hf_repo)
    ms_url = f"https://modelscope.cn/models/{ms_repo}"
    if ms_url not in hf_txt:
        new_hf = hf_txt
        receipt_line = (f"- Full card (bilingual, 训练/评估全量收据): "
                        f"[ModelScope {ms_repo}]({ms_url})\n")
        if "## Receipts" in new_hf:
            new_hf = new_hf.replace("## Receipts\n\n", "## Receipts\n\n" + receipt_line, 1)
        else:
            new_hf = new_hf.rstrip("\n") + "\n\n## Receipts\n\n" + receipt_line
        actions["hf"] = "add-receipt-line"
        hf_new_text = new_hf
    else:
        actions["hf"] = "already-linked"
        hf_new_text = None
    # --- MS 侧 ---
    ms_txt = _http_read(f"https://modelscope.cn/api/v1/models/{ms_repo}"
                        f"/repo?Revision=master&FilePath=README.md")
    hf_url = f"https://huggingface.co/{hf_repo}"
    if hf_url not in ms_txt:
        xlink = (f"> 🔗 跨平台：Hugging Face 英文卡 [{hf_repo}]({hf_url})"
                 f"（HF 卡为英文精选版，本卡为中文全量版）\n\n")
        m = re.search(r"^## ", ms_txt, re.M)
        if m:
            ms_new_text = ms_txt[:m.start()] + xlink + ms_txt[m.start():]
        else:
            ms_new_text = ms_txt.rstrip("\n") + "\n\n" + xlink
        actions["ms"] = "add-xlink"
    else:
        actions["ms"] = "already-linked"
        ms_new_text = None

    if not yes:
        return {"ok": True, "dry_run": True, "actions": actions}
    # 写 HF
    if hf_new_text:
        tmp = os.path.join(tempfile.gettempdir(), "trihub-link-hf.md")
        open(tmp, "w").write(hf_new_text)
        _hf().upload_file(path_or_fileobj=tmp, path_in_repo="README.md", repo_id=hf_repo,
                          repo_type="model", commit_message=f"trihub link: + ModelScope full card")
    # 写 MS（SDK 全关键字，坑已记录）
    if ms_new_text:
        from modelscope.hub.api import HubApi
        ms = HubApi()
        ms.login(open(os.path.expanduser("~/.modelscope/token")).read().strip())
        tmp2 = os.path.join(tempfile.gettempdir(), "trihub-link-ms.md")
        open(tmp2, "w").write(ms_new_text)
        ms.upload_file(repo_id=ms_repo, path_or_fileobj=tmp2, path_in_repo="README.md",
                       commit_message="trihub link: + HuggingFace EN card")
    # 终证
    v_hf = _verify_hf(hf_repo, ms_url) if hf_new_text else True
    v_ms = ms_url and (hf_url in _http_read(
        f"https://modelscope.cn/api/v1/models/{ms_repo}/repo?Revision=master&FilePath=README.md"))
    return {"ok": bool(v_hf and v_ms), "verified": bool(v_hf and v_ms), "actions": actions}


# ============ 3. publish：魔搭 → HF 镜像 ============
def publish_ms_to_hf(ms_repo: str, hf_repo: str | None = None, private: bool = False,
                     yes: bool = False, exist_ok: bool = True):
    """全量镜像：建仓 + snapshot_download + upload_folder + 卡搬运 + 跨平台行。"""
    from modelscope.hub.snapshot_download import snapshot_download
    hf_repo = hf_repo or ms_repo.split("/", 1)[1]
    api = _hf()
    plan = {"create": f"jjshin/{hf_repo}" + (" (private)" if private else ""),
            "weights": f"modelscope snapshot_download({ms_repo!r}) → upload_folder",
            "card": "README 搬运 + 跨平台行 + source 标注"}
    if not yes:
        return {"ok": True, "dry_run": True, "plan": plan}
    url = api.create_repo(f"jjshin/{hf_repo}", repo_type="model", private=private, exist_ok=exist_ok)
    local = snapshot_download(ms_repo)
    api.upload_folder(folder_path=local, repo_id=f"jjshin/{hf_repo}", repo_type="model",
                      commit_message=f"Mirror from ModelScope {ms_repo} (trihub publish)")
    # 卡搬运 + 跨平台行
    ms_txt = _http_read(f"https://modelscope.cn/api/v1/models/{ms_repo}"
                        f"/repo?Revision=master&FilePath=README.md")
    xlink = (f"> 🔁 Mirrored from [ModelScope {ms_repo}]"
             f"(https://modelscope.cn/models/{ms_repo}) · trihub publish\n\n")
    m = re.search(r"^## ", ms_txt, re.M)
    card = (ms_txt[:m.start()] + xlink + ms_txt[m.start():]) if m else ms_txt + "\n\n" + xlink
    tmp = os.path.join(tempfile.gettempdir(), "trihub-publish-card.md")
    open(tmp, "w").write(card)
    api.upload_file(path_or_fileobj=tmp, path_in_repo="README.md", repo_id=f"jjshin/{hf_repo}",
                    repo_type="model", commit_message="Card: mirror note + ModelScope source")
    # 终证：文件在 + 卡含镜像行
    from huggingface_hub import list_repo_files
    files = list_repo_files(f"jjshin/{hf_repo}", repo_type="model")
    ok = len(files) > 2 and _verify_hf(f"jjshin/{hf_repo}", "Mirrored from")
    return {"ok": ok, "verified": ok, "repo": f"jjshin/{hf_repo}",
            "n_files": len(files), "url": f"https://huggingface.co/jjshin/{hf_repo}"}
