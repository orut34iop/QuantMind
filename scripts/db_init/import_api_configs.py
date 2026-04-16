import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

def get_db_url():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    host = os.getenv("DB_MASTER_HOST") or os.getenv("DB_HOST")
    port = os.getenv("DB_MASTER_PORT") or os.getenv("DB_PORT")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    db = os.getenv("DB_NAME")
    missing = [k for k, v in (("DB_HOST", host), ("DB_PORT", port), ("DB_USER", user), ("DB_PASSWORD", password), ("DB_NAME", db)) if not v]
    if missing:
        raise RuntimeError(f"Missing DB env vars: {', '.join(missing)}. Please set DATABASE_URL or DB_* in root .env")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


DB_URL = get_db_url()


async def import_configs():
    engine = create_async_engine(DB_URL)

    # 定义从 api.md 提取的配置数据
    configs = [
        # 1. 阿里千问 (Qwen)
        (
            "QWEN_API_KEY",
            "REMOVED_QWEN_API_KEY",
            "global",
            "ml",
            "阿里千问API密钥",
            True,
        ),
        (
            "QWEN_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "global",
            "ml",
            "阿里千问基础URL",
            False,
        ),
        ("QWEN_MODEL_ID", "qwen3-max", "global", "ml", "阿里千问模型ID", False),
        # 2. 阿里云短信
        (
            "ALISMS_ACCESS_KEY_ID",
            "REMOVED_ALISMS_ACCESS_KEY_ID",
            "global",
            "auth",
            "阿里云短信AccessKey ID",
            True,
        ),
        (
            "ALISMS_ACCESS_KEY_SECRET",
            "REMOVED_ALISMS_ACCESS_KEY_SECRET",
            "global",
            "auth",
            "阿里云短信AccessKey Secret",
            True,
        ),
        ("ALISMS_SIGN_NAME", "方舟量化", "global", "auth", "阿里云短信签名", False),
        # 3. Gemini
        (
            "GEMINI_API_KEY",
            "REMOVED_GEMINI_API_KEY",
            "global",
            "ml",
            "Google Gemini API密钥",
            True,
        ),
        # 4. DeepSeek
        (
            "DEEPSEEK_API_KEY",
            "REMOVED_DEEPSEEK_API_KEY",
            "global",
            "ml",
            "DeepSeek API密钥",
            True,
        ),
        # 5. 智谱AI (GLM)
        (
            "ZHIPU_API_KEY",
            "REMOVED_ZHIPU_API_KEY",
            "global",
            "ml",
            "智谱AI API密钥",
            True,
        ),
        # 6. 硅基流动
        (
            "SILICONFLOW_API_KEY",
            "REMOVED_SILICONFLOW_API_KEY",
            "global",
            "ml",
            "硅基流动API密钥",
            True,
        ),
        # 7. 百度文心一言
        (
            "ERNIE_API_KEY",
            "REMOVED_ERNIE_API_KEY",
            "global",
            "ml",
            "文心一言API密钥",
            True,
        ),
    ]

    async with engine.begin() as conn:
        for key, val, svc, cat, desc, secret in configs:
            stmt = text("""
                INSERT INTO system_settings (config_key, config_value, service_name, category, description, is_secret, updated_at)
                VALUES (:key, :val, :svc, :cat, :desc, :secret, NOW())
                ON CONFLICT (config_key, service_name) DO UPDATE SET
                    config_value = EXCLUDED.config_value,
                    description = EXCLUDED.description,
                    is_secret = EXCLUDED.is_secret,
                    updated_at = NOW()
            """)
            await conn.execute(
                stmt,
                {
                    "key": key,
                    "val": val,
                    "svc": svc,
                    "cat": cat,
                    "desc": desc,
                    "secret": secret,
                },
            )
        print(f"✅ 成功导入 {len(configs)} 项 API 配置到数据库")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(import_configs())
