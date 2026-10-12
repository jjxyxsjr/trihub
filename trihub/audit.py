"""对账引擎：同名仓匹配 + 卡面要素 + 跨平台链 + 缺口清单。"""
from __future__ import annotations
from collections import defaultdict
from .platforms import list_github, list_hf, list_ms

MODEL_CARD_FIELDS = ["license", "base_model", "pipeline_tag", "library_name"]


def gather(gh_owner, hf_owner, ms_owner):
    return {"github": list_github(gh_owner), "hf": list_hf(hf_owner), "ms": list_ms(ms_owner)}


def _norm(name: str):
    return name.lower().replace("_", "-")


def audit(gh_owner, hf_owner, ms_owner):
    data = gather(gh_owner, hf_owner, ms_owner)
    by_name = defaultdict(dict)  # norm_name -> {platform: repo}
    for plat, repos in data.items():
        for r in repos:
            by_name[_norm(r["name"])][plat] = r

    findings = []
    coverage = {"only_hf_ms": [], "only_ms": [], "only_gh": [], "all": [], "hf_no_ms": [], "ms_no_hf": []}

    for key, plats in sorted(by_name.items()):
        present = set(plats)
        if {"hf", "ms"} <= present: coverage["all"].append(key)
        if "ms" in present and "hf" not in present: coverage["ms_no_hf"].append((key, plats["ms"]))
        if "hf" in present and "ms" not in present and plats["hf"]["kind"] == "model":
            coverage["hf_no_ms"].append((key, plats["hf"]))
        if "gh" in present and len(present) == 1: coverage["only_gh"].append(key)

        # 卡面要素（HF 模型）
        if "hf" in present and plats["hf"]["kind"] == "model":
            cf = plats["hf"]["card_fields"]
            if cf:
                missing = [f for f in MODEL_CARD_FIELDS if not cf.get(f)]
                if missing and plats["hf"]["name"] != hf_owner:
                    findings.append(("card_missing", "hf", plats["hf"]["full"], missing))

        # 跨平台回链检查（王牌仓才严格要求双向链）
        for plat, other_plat, other_owner in (("hf", "ms", ms_owner), ("ms", "hf", hf_owner)):
            if plat in present and other_plat in present:
                want = f"{other_owner.lower()}/{_norm(plats[other_plat]['name'])}"
                links = plats[plat]["links"][other_plat]
                # 归一化链接比对
                hit = any(want.split("/")[1].split("-")[0] in l.replace("_", "-") for l in links)
                # 仅对明确同名王牌仓报
                if not links and plats[plat]["name"] not in (gh_owner,):
                    findings.append(("no_xlink", plat, plats[plat]["full"], other_plat))

        # 残链
        for plat in present:
            for b in plats[plat]["links"]["broken"]:
                findings.append(("broken_link", plat, plats[plat]["full"], b))

    return data, by_name, coverage, findings
