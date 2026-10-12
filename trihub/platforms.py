"""三平台只读后端：返回统一的 Repo 结构。所有调用只走公开 API/免 token 通道。"""
from __future__ import annotations
import os, re, json, subprocess, urllib.request, urllib.parse

PROXIES = {"http": os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7897"),
           "https": os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7897")} if os.environ.get("USE_PROXY", "1") == "1" else None

REPO = dict  # {platform, owner, name, full, url, private, desc, readme, card_fields, links}

# 链接里可识别的跨平台目标
RX_GH = re.compile(r"https?://github\.com/([\w.-]+)/([\w.-]+)")
RX_HF = re.compile(r"https?://huggingface\.co/(?:spaces/)?([\w.-]+)/([\w.-]+)")
RX_MS = re.compile(r"https?://modelscope\.cn/(?:models/)?([\w.-]+)/([\w.-]+)")
RX_BROKEN = [
    re.compile(r"https?://modelscope\.cn/collections\b(?!/[A-Za-z0-9_-]{6,})"),  # 残链：合集根
]


def _http_json(url, headers=None, method="GET", body=None):
    h = {"User-Agent": "trihub/0.1", **(headers or {})}
    req = urllib.request.Request(url, method=method, headers=h,
                                 data=json.dumps(body).encode() if body else None)
    if body: h["Content-Type"] = "application/json"
    proxy = urllib.request.ProxyHandler(PROXIES or {})
    ctx = urllib.request.build_opener(proxy)
    with ctx.open(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _extract_links(readme: str):
    links = {"github": set(), "hf": set(), "ms": set(), "broken": []}
    if not readme:
        return links
    for o, n in RX_GH.findall(readme): links["github"].add(f"{o}/{n}".lower())
    for o, n in RX_HF.findall(readme): links["hf"].add(f"{o}/{n}".lower())
    for o, n in RX_MS.findall(readme):
        if o not in ("models", "datasets", "studios", "posts", "collections", "api"):
            links["ms"].add(f"{o}/{n}".lower())
    for rx in RX_BROKEN:
        for m in rx.findall(readme): links["broken"].append(m if isinstance(m, str) else m[0])
    links["github"] = sorted(links["github"]); links["hf"] = sorted(links["hf"]); links["ms"] = sorted(links["ms"])
    return links


def _frontmatter(readme: str):
    if not readme or not readme.startswith("---"):
        return {}
    end = readme.find("\n---", 3)
    if end < 0:
        return {}
    fm = readme[4:end]
    keys = set()
    for line in fm.splitlines():
        m = re.match(r"^([a-zA-Z_]+):", line)
        if m: keys.add(m.group(1))
    return {k: (k in keys) for k in
            ["license", "base_model", "pipeline_tag", "model-index", "library_name", "tags", "sdk"]}


# ---------------- GitHub（纯 REST，gh CLI 非必需；GITHUB_TOKEN 可选提限额/私有仓）----------------
_GH_TOKEN = None

def _gh_token():
    """GITHUB_TOKEN 优先；否则取本机 gh 登录态（创空间无 gh 则匿名）。"""
    global _GH_TOKEN
    if _GH_TOKEN is not None:
        return _GH_TOKEN
    _GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
    if not _GH_TOKEN:
        try:
            r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=8)
            if r.returncode == 0:
                _GH_TOKEN = r.stdout.strip()
        except Exception:
            pass
    return _GH_TOKEN


def _gh_get(url: str):
    headers = {"User-Agent": "trihub/0.2", "Accept": "application/vnd.github+json"}
    tok = _gh_token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, headers=headers)
    # GitHub API 直连：Clash 共享出口 IP 常被限流（403 rate limit）；api.github.com 本机直连可达。
    # 创空间等国内环境若直连不通，GitHub 列会降级为空（体检主体 HF/MS 不受影响）。
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open(req, timeout=20) as r:
        return json.loads(r.read().decode())


def list_github(owner: str):
    out, page = [], 1
    while True:
        try:
            data = _gh_get(f"https://api.github.com/users/{owner}/repos"
                           f"?per_page=100&page={page}&type=all&sort=updated")
        except Exception:
            break
        if not data or not isinstance(data, list):
            break
        for d in data:
            if d.get("fork"):
                continue
            out.append(_gh_repo(d))
        if len(data) < 100:
            break
        page += 1
        if page > 10:
            break
    return out


def _gh_repo(d: dict):
    import base64
    readme = ""
    try:
        r = _gh_get(f"https://api.github.com/repos/{d['full_name']}/readme")
        readme = base64.b64decode(r["content"]).decode("utf-8", "ignore")
    except Exception:
        pass
    return {"platform": "github", "owner": d["owner"]["login"], "name": d["name"],
            "full": d["full_name"], "url": d["html_url"], "private": d["private"],
            "desc": d.get("description") or "", "readme": readme,
            "card_fields": {}, "links": _extract_links(readme)}


# ---------------- Hugging Face ----------------
def list_hf(owner: str):
    from huggingface_hub import HfApi
    api = HfApi()
    repos = []
    for kind in ("model", "space", "dataset"):
        try:
            infos = (api.list_models(author=owner) if kind == "model" else
                     api.list_spaces(author=owner) if kind == "space" else
                     api.list_datasets(author=owner))
            for info in infos:
                if info.id == f"{owner}/{owner}":  # 自名索引卡也保留但标记
                    pass
                readme = ""
                try:
                    p = api.hf_hub_download(info.id, "README.md", repo_type=kind, force_download=True)
                    readme = open(p, encoding="utf-8").read()
                except Exception:
                    pass
                repos.append({"platform": "hf", "owner": owner, "name": info.id.split("/", 1)[1],
                              "full": info.id, "kind": kind,
                              "url": f"https://huggingface.co/{info.id}", "private": False,
                              "desc": getattr(info, "pipeline_tag", None) or "", "readme": readme,
                              "card_fields": _frontmatter(readme), "links": _extract_links(readme)})
        except Exception as e:
            print(f"  [warn] hf {kind}: {e}")
    return repos


# ---------------- ModelScope ----------------
def list_ms(owner: str):
    from modelscope.hub.api import HubApi
    api = HubApi()
    repos = []
    page = 1
    while True:
        d = api.list_models(owner, page_number=page, page_size=100)
        for m in d.get("Models", []):
            mid = m.get("model_id") or f"{m.get('Path','')}/{m.get('Name','')}"
            name = mid.split("/", 1)[1] if "/" in mid else mid
            readme = ""
            try:
                url = (f"https://modelscope.cn/api/v1/models/{owner}/{name}"
                       f"/repo?Revision=master&FilePath=README.md")
                req = urllib.request.Request(url, headers={"User-Agent": "trihub/0.1"})
                op = urllib.request.build_opener(urllib.request.ProxyHandler(PROXIES or {}))
                with op.open(req, timeout=30) as r:
                    readme = r.read().decode("utf-8", "ignore")
            except Exception:
                pass
            repos.append({"platform": "ms", "owner": owner, "name": name,
                          "full": f"{owner}/{name}", "kind": "model",
                          "url": f"https://modelscope.cn/models/{owner}/{name}", "private": False,
                          "desc": (m.get("ChineseName") or m.get("Description") or "") if isinstance(m, dict) else "",
                          "readme": readme, "card_fields": _frontmatter(readme),
                          "links": _extract_links(readme)})
        if len(repos) >= d.get("TotalCount", 0) or not d.get("Models"):
            break
        page += 1
    return repos
