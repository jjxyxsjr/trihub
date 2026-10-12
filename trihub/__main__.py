import sys, argparse
from .audit import audit


def main():
    ap = argparse.ArgumentParser(prog="trihub", description="GitHub/HF/ModelScope 作品位对账（只读）")
    ap.add_argument("--gh", default="jjxyxsjr")
    ap.add_argument("--hf", default="jjshin")
    ap.add_argument("--ms", default="theGAI")
    a = ap.parse_args()

    print(f"trihub v0.1 只读对账  ·  GH {a.gh} | HF {a.hf} | MS {a.ms}\n")
    data, by_name, cov, findings = audit(a.gh, a.hf, a.ms)
    for p, repos in data.items():
        print(f"  {p:7s} {len(repos)} 仓（去 fork）")

    print(f"\n══ 同名覆盖（HF∩MS 模型）{len(cov['all'])} 个 ══")
    for k in cov["all"]:
        plats = by_name[k]
        marks = "".join(p[0].upper() for p in ("github", "hf", "ms") if p in plats)
        print(f"  [{marks:3s}] {plats[list(plats)[0]]['full'].split('/')[0]}/{k}")

    print(f"\n══ 只在 MS 没镜像到 HF：{len(cov['ms_no_hf'])} 个（前 15）══")
    for k, r in cov["ms_no_hf"][:15]:
        print(f"  · {r['full']}")

    print(f"\n══ 问题清单 {len(findings)} 条 ══")
    seen = set()
    for kind, plat, full, detail in findings:
        sig = (kind, full, str(detail))
        if sig in seen: continue
        seen.add(sig)
        icon = {"card_missing": "🪪", "no_xlink": "🔗", "broken_link": "💔"}.get(kind, "?")
        print(f"  {icon} [{plat}] {full}  → {kind}: {detail}")


if __name__ == "__main__":
    main()
