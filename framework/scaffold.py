#!/usr/bin/env python3
"""项目脚手架：一条命令生成一个本体项目骨架。

用法：
  python3 scaffold.py --name supplier-compliance --title "供应商合规审查" \
      --base-iri "https://example.com/sc#"

生成 projects/<name>/，内置：目录规范、模板文件（占位符已替换）、
通用 run_cq.py / check_ghost.py / agent.py / ci.sh。
"""
import argparse
import shutil
import stat
from pathlib import Path

FRAMEWORK_DIR = Path(__file__).parent
TEMPLATES = FRAMEWORK_DIR / "templates"


def render(text, ctx):
    for k, v in ctx.items():
        text = text.replace("{{%s}}" % k, v)
    return text


def main():
    ap = argparse.ArgumentParser(description="本体项目脚手架")
    ap.add_argument("--name", required=True, help="项目名（英文小写连字符，如 supplier-compliance）")
    ap.add_argument("--title", required=True, help="项目中文名（如 供应商合规审查）")
    ap.add_argument("--base-iri", required=True, help="本体命名空间 IRI，# 结尾")
    ap.add_argument("--root", default=str(FRAMEWORK_DIR / "projects"), help="项目根目录")
    args = ap.parse_args()

    if not args.base_iri.endswith("#"):
        ap.error("--base-iri 必须以 # 结尾")

    target = Path(args.root) / args.name
    if target.exists():
        ap.error("项目已存在：%s" % target)

    ctx = {
        "PROJECT_NAME": args.name,
        "PROJECT_TITLE": args.title,
        "BASE_IRI": args.base_iri,
        "BASE_IRI_NOHASH": args.base_iri.rstrip("#"),
    }

    for src in TEMPLATES.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(TEMPLATES)
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        content = src.read_text(encoding="utf-8")
        dst.write_text(render(content, ctx), encoding="utf-8")

    # 运行期目录
    for d in ("data", "proposals", "versions"):
        (target / d).mkdir(parents=True, exist_ok=True)
    # ci.sh 可执行
    (target / "ci.sh").chmod((target / "ci.sh").stat().st_mode | stat.S_IEXEC)

    print("✅ 项目骨架已生成：%s" % target)
    print("""
下一步（按 framework/README.md §3 的九站流程）：
  S1-S2  编辑 cq/competency_questions.md，写下 5-8 个业务问题
  S3     编辑 glossary.md，裁决术语口径
  S4-S6  编辑 ontology/domain.ttl，建类/属性/公理
  S7     数据接入（手写 data/catalog.ttl 或接 Ontop 映射）
  S8     编辑 ontology/shapes.ttl，写硬规则
  S9     python3 run_cq.py && bash ci.sh   # 验收门禁
""")


if __name__ == "__main__":
    main()
