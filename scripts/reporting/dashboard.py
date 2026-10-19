"""从 Clean 层生成 CSV、Markdown 与单文件 Plotly Dashboard。"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def generate_dashboard(
    clean_rows: list[dict[str, Any]],
    issue_rows: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Path]:
    """生成与当前数据库查询结果绑定的可复现报告。"""
    try:
        import pandas as pd
        import plotly.express as px
        from plotly.io import to_html
    except ImportError as exc:
        raise RuntimeError("缺少 pandas 或 plotly，请先安装 requirements.txt") from exc
    if not clean_rows:
        raise ValueError("Clean 层没有可用于报告的数据")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    clean = pd.DataFrame(clean_rows)
    issues = pd.DataFrame(issue_rows, columns=(
        "issue_key", "city", "business_date", "field_name", "issue_code",
        "severity", "original_value", "message",
    ))
    clean["business_date"] = pd.to_datetime(clean["business_date"])
    clean.to_csv(output_dir / "clean_air_quality.csv", index=False, encoding="utf-8-sig")
    issues.to_csv(output_dir / "quality_issues.csv", index=False, encoding="utf-8-sig")

    summary = clean.groupby("city", as_index=False).agg(
        record_count=("business_date", "count"), average_aqi=("aqi", "mean"),
        missing_records=("has_missing", "sum"),
    )
    summary.to_csv(output_dir / "city_summary.csv", index=False, encoding="utf-8-sig")

    trend = px.line(clean, x="business_date", y="aqi", color="city", markers=True,
                    title="五城市 AQI 趋势")
    average = px.bar(summary, x="city", y="average_aqi", color="city",
                     title="城市平均 AQI 对比")
    if issues.empty:
        issue_section = "<p>当前查询结果未发现质量问题。</p>"
    else:
        issue_counts = issues.groupby("issue_code", as_index=False).size()
        issue_chart = px.bar(issue_counts, x="issue_code", y="size", color="issue_code",
                             title="数据质量问题分布")
        issue_section = to_html(issue_chart, full_html=False, include_plotlyjs=False)

    start = clean["business_date"].min().date().isoformat()
    end = clean["business_date"].max().date().isoformat()
    dashboard = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>空气质量 ETL Dashboard</title>
<style>body{{font-family:Arial,"Microsoft YaHei",sans-serif;max-width:1200px;margin:auto;padding:24px}}.cards{{display:flex;gap:16px;flex-wrap:wrap}}.card{{background:#f3f6fa;border-radius:10px;padding:16px;min-width:180px}}h1{{color:#17324d}}</style></head>
<body><h1>多城市空气质量 ETL Dashboard</h1><div class="cards">
<div class="card"><b>记录数</b><br>{len(clean)}</div>
<div class="card"><b>城市数</b><br>{clean['city'].nunique()}</div>
<div class="card"><b>日期范围</b><br>{html.escape(start)} 至 {html.escape(end)}</div>
<div class="card"><b>质量问题</b><br>{len(issues)}</div></div>
{to_html(trend, full_html=False, include_plotlyjs=True)}
{to_html(average, full_html=False, include_plotlyjs=False)}
{issue_section}</body></html>"""
    (output_dir / "dashboard.html").write_text(dashboard, encoding="utf-8")

    report = (
        "# 空气质量 ETL 运行报告\n\n"
        f"- 清洗记录数：{len(clean)}\n- 城市数：{clean['city'].nunique()}\n"
        f"- 日期范围：{start} 至 {end}\n- 质量问题数：{len(issues)}\n"
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    return {name: output_dir / name for name in (
        "dashboard.html", "clean_air_quality.csv", "quality_issues.csv",
        "city_summary.csv", "report.md"
    )}
