import sys, argparse, json
from .audit import audit
from . import ops


def cmd_audit(a):
    print(f"trihub v0.2 只读对账  ·  GH {a.gh} | HF {a.hf} | MS {a.ms}\n")
    data, by_name, cov, findings = audit(a.gh, a.hf, a.ms)
    for p, repos in data.items():
        print(f"  {p:7s} {len(repos)} 仓（去 fork）")
    print(f"\n══ 同名覆盖（HF∩MS）{len(cov['all'])} 个 ══")
    for k in cov["all"]:
        plats = by_name[k]
        marks = "".join(p[0].upper() for p in ("github", "hf", "ms") if p in plats)
        print(f"  [{marks:3s}] {k}")
    print(f"\n══ 只在 MS 没镜像 HF：{len(cov['ms_no_hf'])} 个（前 15）══")
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


def cmd_fix_card(a):
    fields = json.loads(a.fields)
    r = ops.fix_card(a.repo, fields, yes=a.yes)
    print(json.dumps(r, ensure_ascii=False, indent=1))


def cmd_link(a):
    r = ops.link_pair(a.ms, a.hf, yes=a.yes)
    print(json.dumps(r, ensure_ascii=False, indent=1))


def cmd_publish(a):
    r = ops.publish_ms_to_hf(a.ms_repo, a.hf_name, private=a.private, yes=a.yes)
    print(json.dumps(r, ensure_ascii=False, indent=1))


def cmd_studio_push(a):
    r = ops.push_studio(a.owner, a.name, a.dir, revision=a.revision, yes=a.yes)
    print(json.dumps(r, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(prog="trihub",
        description="GitHub/HF/ModelScope 作品位对账与操控。写操作默认 dry-run，--yes 才执行。")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_audit = sub.add_parser("audit", help="只读对账")
    ap_audit.add_argument("--gh", default="jjxyxsjr"); ap_audit.add_argument("--hf", default="jjshin")
    ap_audit.add_argument("--ms", default="theGAI"); ap_audit.set_defaults(f=cmd_audit)

    ap_fix = sub.add_parser("fix-card", help="补 HF 卡 frontmatter 字段")
    ap_fix.add_argument("repo"); ap_fix.add_argument("--fields", required=True,
        help='JSON，如 \'{"pipeline_tag":"text-generation"}\'')
    ap_fix.add_argument("--yes", action="store_true"); ap_fix.set_defaults(f=cmd_fix_card)

    ap_link = sub.add_parser("link", help="跨平台回链补齐（幂等）")
    ap_link.add_argument("--ms", required=True); ap_link.add_argument("--hf", required=True)
    ap_link.add_argument("--yes", action="store_true"); ap_link.set_defaults(f=cmd_link)

    ap_pub = sub.add_parser("publish", help="魔搭 → HF 全量镜像")
    ap_pub.add_argument("ms_repo"); ap_pub.add_argument("--hf-name")
    ap_pub.add_argument("--private", action="store_true")
    ap_pub.add_argument("--yes", action="store_true"); ap_pub.set_defaults(f=cmd_publish)

    ap_sp = sub.add_parser("studio-push", help="推整个目录到网页创建的 git-backed Studio")
    ap_sp.add_argument("owner"); ap_sp.add_argument("name"); ap_sp.add_argument("dir")
    ap_sp.add_argument("--revision", default="master")
    ap_sp.add_argument("--yes", action="store_true"); ap_sp.set_defaults(f=cmd_studio_push)

    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
