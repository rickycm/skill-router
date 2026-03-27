#!/usr/bin/env python3
"""config.py — 配置加载（支持 .env 或 OpenClaw 配置）"""

import os
from pathlib import Path
from dataclasses import dataclass

# 尝试加载 python-dotenv
try:
    from dotenv import load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False


DEFAULT_BASE_URL = "https://ai.gitee.com/v1"
DEFAULT_MODEL = "Qwen3-Embedding-0.6B"
DEFAULT_DIMENSIONS = 1024


def _skill_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _skills_pool_dir() -> Path:
    """skills 资源池路径（被检索但不被 OpenClaw 扫描）"""
    return _skill_dir() / ".skills-pool"


def _try_load_env():
    """尝试加载 .env 文件"""
    env_path = _skill_dir() / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        env_example = _skill_dir() / ".env.example"
        if env_example.exists():
            load_dotenv(env_example)


@dataclass
class Config:
    embedding_provider: str
    embedding_api_key: str
    embedding_base_url: str
    embedding_model: str
    embedding_dimensions: int
    db_path: Path
    vectors_path: Path
    default_top_k: int
    min_score_threshold: float

    @classmethod
    def from_env(cls) -> "Config":
        """优先从 .env 加载"""
        _try_load_env()

        provider = os.getenv("EMBEDDING_PROVIDER", "openai")
        api_key = os.getenv("OPENAI_API_KEY", os.getenv("OLLAMA_API_KEY", ""))
        base_url = os.getenv("OPENAI_BASE_URL", os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL))
        model = os.getenv("OPENAI_MODEL", os.getenv("OLLAMA_MODEL", DEFAULT_MODEL))
        dimensions = int(os.getenv("OPENAI_DIMENSIONS", os.getenv("OLLAMA_DIMENSIONS", DEFAULT_DIMENSIONS)))
        top_k = int(os.getenv("DEFAULT_TOP_K", "5"))
        threshold = float(os.getenv("MIN_SCORE_THRESHOLD", "0.3"))

        skill_dir = _skill_dir()
        data_dir = os.getenv("DATA_DIR", "./data")
        data_path = skill_dir / data_dir

        return cls(
            embedding_provider=provider,
            embedding_api_key=api_key,
            embedding_base_url=base_url,
            embedding_model=model,
            embedding_dimensions=dimensions,
            db_path=data_path / "skill_embeddings.db",
            vectors_path=data_path / "vectors.npy",
            default_top_k=top_k,
            min_score_threshold=threshold,
        )

    @classmethod
    def from_openclaw(cls) -> "Config":
        """从 OpenClaw 配置读取 API Key"""
        import json

        api_key = ""
        base_url = DEFAULT_BASE_URL
        model = DEFAULT_MODEL

        oc_cfg = Path.home() / ".openclaw/openclaw.json"
        try:
            with open(oc_cfg) as f:
                c = json.load(f)
            remote = c.get("agents", {}).get("defaults", {}).get("memorySearch", {}).get("remote", {})
            api_key = remote.get("apiKey", "")
            if api_key == "__OPENCLAW_REDACTED__":
                api_key = ""
            base_url = remote.get("baseUrl", DEFAULT_BASE_URL)
            model = c.get("agents", {}).get("defaults", {}).get("memorySearch", {}).get("model", DEFAULT_MODEL)
        except Exception:
            pass

        for var in ["GITEE_API_KEY", "OPENAI_API_KEY"]:
            k = os.environ.get(var, "")
            if k:
                api_key = k

        skill_dir = _skill_dir()
        return cls(
            embedding_provider="openai",
            embedding_api_key=api_key,
            embedding_base_url=base_url,
            embedding_model=model,
            embedding_dimensions=DEFAULT_DIMENSIONS,
            db_path=skill_dir / "data" / "skill_embeddings.db",
            vectors_path=skill_dir / "data" / "vectors.npy",
            default_top_k=5,
            min_score_threshold=0.3,
        )

    @classmethod
    def create(cls) -> "Config":
        """工厂方法：优先 .env，fallback OpenClaw"""
        env_path = _skill_dir() / ".env"
        if env_path.exists():
            return cls.from_env()
        return cls.from_openclaw()
