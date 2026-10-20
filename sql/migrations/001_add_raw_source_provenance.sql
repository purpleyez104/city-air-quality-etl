-- 仅供已存在的项目数据库在获得明确 DDL 授权后执行。
-- 执行前应备份并确认 raw_air_quality 没有未识别的来源类型。
ALTER TABLE raw_air_quality
    ADD COLUMN source_type VARCHAR(32) NOT NULL DEFAULT 'cnemc_api' AFTER snapshot_batch_id,
    ADD COLUMN source_record_key VARCHAR(128) NULL AFTER source_type,
    ADD COLUMN observation_hour TINYINT UNSIGNED NULL AFTER business_date,
    ADD COLUMN source_file VARCHAR(255) NULL AFTER observation_hour;

UPDATE raw_air_quality
SET source_record_key = CONCAT('cnemc_api:', city_code, ':', source_id)
WHERE source_record_key IS NULL;

ALTER TABLE raw_air_quality
    MODIFY COLUMN source_record_key VARCHAR(128) NOT NULL,
    DROP INDEX uk_raw_source,
    ADD UNIQUE KEY uk_raw_source_record (source_type, source_record_key);
