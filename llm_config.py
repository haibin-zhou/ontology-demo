"""LLM 配置与凭证加载（ontology-demo 自包含版）。

凭证来源（按优先级）：
  1. 环境变量 KIMI_API_KEY
  2. 本目录下的 .env 文件（已 gitignore，参考 .env.example）

模型/BASE_URL 可用环境变量覆盖：KIMI_MODEL / KIMI_FALLBACK_MODEL / KIMI_BASE_URL。
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

KIMI_BASE_URL = os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
KIMI_MODEL = os.environ.get("KIMI_MODEL", "kimi-k3")
# 主模型不可用时回退到同系可用模型
KIMI_FALLBACK_MODEL = os.environ.get("KIMI_FALLBACK_MODEL", "kimi-k2.5")

# 成本估算单价（元，按公开定价粗估，仅用于台账参考）
COST = {
    "kimi_input_per_mtok": 4.0,
    "kimi_output_per_mtok": 16.0,
}


def load_env(path=ENV_PATH):
    """手动解析 .env，返回 dict；同时注入 os.environ（不覆盖已存在的变量）。"""
    env = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    env[key] = value
                    os.environ.setdefault(key, value)
    return env


def get(key, default=None):
    """优先读 os.environ，其次解析 .env。"""
    if key in os.environ:
        return os.environ[key]
    return load_env().get(key, default)


def require(key):
    value = get(key)
    if not value:
        raise RuntimeError(
            "缺少凭证 %s：请设置环境变量，或在 %s 中配置（参考 .env.example）"
            % (key, ENV_PATH))
    return value
