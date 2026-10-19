"""MySQL 数据访问层；所有写入均限制在项目自有表。"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from scripts.config import MySQLSettings
from scripts.ingestion.response_normalizer import NormalizedAirQualityRecord
from scripts.processing.quality import CleanRecord, QualityIssue


class RepositoryError(RuntimeError):
    """表示 MySQL 连接或项目表读写失败。"""


class MySQLRepository:
    """封装项目四张表的初始化、查询和幂等写入。"""

    def __init__(self, settings: MySQLSettings) -> None:
        self.settings = settings

    def connect(self):
        """创建显式事务连接；调用方负责关闭。"""
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ImportError as exc:
            raise RepositoryError("缺少 PyMySQL，请先安装 requirements.txt") from exc
        try:
            return pymysql.connect(
                host=self.settings.host, port=self.settings.port,
                user=self.settings.user, password=self.settings.password,
                database=self.settings.database, charset="utf8mb4",
                autocommit=False, cursorclass=DictCursor,
            )
        except Exception as exc:
            raise RepositoryError(f"MySQL 连接失败: {exc}") from exc

    def initialize_schema(self, schema_path: Path) -> None:
        """仅执行仓库中经过审查的 CREATE TABLE IF NOT EXISTS。"""
        statements = [part.strip() for part in schema_path.read_text(encoding="utf-8").split(";") if part.strip()]
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise RepositoryError(f"Schema 初始化失败: {exc}") from exc
        finally:
            connection.close()

    def upsert_raw(self, batch_id: str, records: Iterable[NormalizedAirQualityRecord]) -> int:
        """按来源城市与来源 ID 幂等导入 Raw 结构化记录。"""
        sql = """
        INSERT INTO raw_air_quality (
          snapshot_batch_id, source_id, city_code, city, source_area, business_date,
          source_time_point, source_time_point_text, aqi, pm10, pm2_5, so2, co, no2, o3,
          primary_pollutant, quality, health_advice, activity_advice
        ) VALUES (
          %(snapshot_batch_id)s, %(source_id)s, %(city_code)s, %(city)s, %(source_area)s,
          %(business_date)s, %(source_time_point)s, %(source_time_point_text)s, %(aqi)s,
          %(pm10)s, %(pm2_5)s, %(so2)s, %(co)s, %(no2)s, %(o3)s,
          %(primary_pollutant)s, %(quality)s, %(health_advice)s, %(activity_advice)s
        ) AS new ON DUPLICATE KEY UPDATE
          snapshot_batch_id=new.snapshot_batch_id, business_date=new.business_date,
          aqi=new.aqi, pm10=new.pm10, pm2_5=new.pm2_5, so2=new.so2, co=new.co,
          no2=new.no2, o3=new.o3, primary_pollutant=new.primary_pollutant,
          quality=new.quality, health_advice=new.health_advice,
          activity_advice=new.activity_advice
        """
        payload = []
        for record in records:
            item = asdict(record)
            item["snapshot_batch_id"] = batch_id
            payload.append(item)
        if not payload:
            return 0
        self._write_many(sql, payload)
        return len(payload)

    def fetch_raw(self, batch_id: str | None = None) -> list[dict[str, Any]]:
        """读取 Raw 层；ETL 不修改该表。"""
        sql = "SELECT * FROM raw_air_quality"
        params: tuple[Any, ...] = ()
        if batch_id:
            sql += " WHERE snapshot_batch_id=%s"
            params = (batch_id,)
        sql += " ORDER BY city, business_date, source_id"
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())
        finally:
            connection.close()

    def start_run(self, run_id: str, batch_id: str | None) -> None:
        self._write_one(
            "INSERT INTO air_quality_etl_runs (run_id,snapshot_batch_id,started_at,status) VALUES (%s,%s,NOW(6),'running')",
            (run_id, batch_id),
        )

    def finish_run(self, run_id: str, input_count: int, output_count: int, issue_count: int) -> None:
        self._write_one(
            "UPDATE air_quality_etl_runs SET finished_at=NOW(6),input_count=%s,output_count=%s,issue_count=%s,status='success' WHERE run_id=%s",
            (input_count, output_count, issue_count, run_id),
        )

    def fail_run(self, run_id: str, message: str) -> None:
        self._write_one(
            "UPDATE air_quality_etl_runs SET finished_at=NOW(6),status='failed',error_message=%s WHERE run_id=%s",
            (message[:1000], run_id),
        )

    def upsert_clean(self, run_id: str, records: Iterable[CleanRecord]) -> int:
        sql = """
        INSERT INTO air_quality (
          city,business_date,aqi,pm10,pm2_5,so2,co,no2,o3,primary_pollutant,
          quality,has_missing,source_raw_id,etl_run_id
        ) VALUES (
          %(city)s,%(business_date)s,%(aqi)s,%(pm10)s,%(pm2_5)s,%(so2)s,%(co)s,
          %(no2)s,%(o3)s,%(primary_pollutant)s,%(quality)s,%(has_missing)s,
          %(source_raw_id)s,%(etl_run_id)s
        ) AS new ON DUPLICATE KEY UPDATE
          aqi=new.aqi,pm10=new.pm10,pm2_5=new.pm2_5,so2=new.so2,co=new.co,
          no2=new.no2,o3=new.o3,primary_pollutant=new.primary_pollutant,
          quality=new.quality,has_missing=new.has_missing,
          source_raw_id=new.source_raw_id,etl_run_id=new.etl_run_id
        """
        payload = []
        for record in records:
            item = asdict(record)
            item["etl_run_id"] = run_id
            payload.append(item)
        if payload:
            self._write_many(sql, payload)
        return len(payload)

    def upsert_issues(self, run_id: str, issues: Iterable[QualityIssue]) -> int:
        sql = """
        INSERT INTO air_quality_quality_log (
          issue_key,etl_run_id,city,business_date,field_name,issue_code,severity,original_value,message
        ) VALUES (
          %(issue_key)s,%(etl_run_id)s,%(city)s,%(business_date)s,%(field_name)s,
          %(issue_code)s,%(severity)s,%(original_value)s,%(message)s
        ) AS new ON DUPLICATE KEY UPDATE etl_run_id=new.etl_run_id,
          original_value=new.original_value,message=new.message,last_seen_at=CURRENT_TIMESTAMP
        """
        payload = []
        for issue in issues:
            item = asdict(issue)
            item["etl_run_id"] = run_id
            payload.append(item)
        if payload:
            self._write_many(sql, payload)
        return len(payload)

    def fetch_dashboard_data(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        clean = self._read("SELECT * FROM air_quality ORDER BY city,business_date")
        issues = self._read("SELECT * FROM air_quality_quality_log ORDER BY city,business_date,field_name")
        return clean, issues

    def _read(self, sql: str) -> list[dict[str, Any]]:
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                return list(cursor.fetchall())
        finally:
            connection.close()

    def _write_one(self, sql: str, params: tuple[Any, ...]) -> None:
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _write_many(self, sql: str, params: list[dict[str, Any]]) -> None:
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                cursor.executemany(sql, params)
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise RepositoryError(f"MySQL 批量写入失败: {exc}") from exc
        finally:
            connection.close()
