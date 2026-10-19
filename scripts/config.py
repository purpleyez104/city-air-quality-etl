"""项目本地配置加载；Secret 只从环境变量或未提交的 ``.env`` 读取。"""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(RuntimeError):
    """表示运行所需配置缺失或格式非法。"""


@dataclass(frozen=True)
class MySQLSettings:
    """MySQL 连接参数，不包含任何默认密码。"""

    host: str
    port: int
    user: str
    password: str
    database: str


def load_mysql_settings() -> MySQLSettings:
    """加载 MySQL 配置并在连接前一次性检查必要字段。"""

    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise ConfigurationError("缺少 python-dotenv，请先安装 requirements.txt") from exc

    load_dotenv()
    values = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1").strip(),
        "port": os.getenv("MYSQL_PORT", "3306").strip(),
        "user": os.getenv("MYSQL_USER", "").strip(),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "").strip(),
    }
    missing = [name for name in ("user", "password", "database") if not values[name]]
    if missing:
        raise ConfigurationError("缺少 MySQL 配置: " + ", ".join(missing))
    try:
        port = int(values["port"])
    except ValueError as exc:
        raise ConfigurationError("MYSQL_PORT 必须是整数") from exc
    if not 1 <= port <= 65535:
        raise ConfigurationError("MYSQL_PORT 必须在 1-65535 之间")
    return MySQLSettings(
        host=values["host"], port=port, user=values["user"],
        password=values["password"], database=values["database"]
    )
