"""从 Clean 与 Raw 血缘生成可复现的 CSV、Markdown 和 Plotly Dashboard。"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any


NUMERIC_FIELDS = ("aqi", "pm10", "pm2_5", "so2", "co", "no2", "o3")
SOURCE_LABELS = {
    "quotsoft_history_csv": "2025 历史 CSV",
    "cnemc_api": "2026 API",
    "snapshot_preview": "Snapshot Preview",
}


def generate_dashboard(
    clean_rows: list[dict[str, Any]],
    issue_rows: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Path]:
    """生成与本次查询结果绑定的六类报告文件。

    数值缺失保持为空，聚合只使用对应字段的有效样本。趋势按来源拆分 Trace，
    因而不会跨历史 CSV 与 API 的时间断档连线。
    """

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
    clean = pd.DataFrame(clean_rows).copy()
    _require_columns(clean, {"city", "business_date", *NUMERIC_FIELDS, "has_missing"})
    clean["business_date"] = pd.to_datetime(clean["business_date"])
    if "source_type" not in clean:
        clean["source_type"] = "snapshot_preview"
    else:
        clean["source_type"] = clean["source_type"].fillna("snapshot_preview")
    clean["source_label"] = clean["source_type"].map(SOURCE_LABELS).fillna(
        clean["source_type"]
    )
    clean["month"] = clean["business_date"].dt.to_period("M").astype(str)
    for field in NUMERIC_FIELDS:
        clean[field] = pd.to_numeric(clean[field], errors="coerce")
    clean["has_missing"] = clean["has_missing"].astype(bool)

    issues = pd.DataFrame(issue_rows).copy()
    if issues.empty:
        issues = pd.DataFrame(
            columns=(
                "issue_key", "city", "business_date", "field_name",
                "issue_code", "severity", "original_value", "message",
            )
        )
    elif "business_date" in issues:
        issues["business_date"] = pd.to_datetime(issues["business_date"])

    city_summary = _build_city_summary(clean)
    monthly_summary = _build_monthly_summary(clean)
    _write_csv_outputs(clean, issues, city_summary, monthly_summary, output_dir)

    charts = _build_charts(clean, issues, city_summary, monthly_summary, px, to_html)
    metrics = _build_metrics(clean, issues)
    dashboard = _render_dashboard(metrics, charts)
    (output_dir / "dashboard.html").write_text(dashboard, encoding="utf-8")
    (output_dir / "report.md").write_text(
        _render_markdown(metrics, city_summary, clean), encoding="utf-8"
    )
    return {
        name: output_dir / name
        for name in (
            "dashboard.html",
            "clean_air_quality.csv",
            "quality_issues.csv",
            "city_summary.csv",
            "monthly_summary.csv",
            "report.md",
        )
    }


def _require_columns(frame, required: set[str]) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError("Clean 数据缺少报告字段: " + ", ".join(missing))


def _build_city_summary(clean):
    return (
        clean.groupby("city", as_index=False)
        .agg(
            record_count=("business_date", "count"),
            date_min=("business_date", "min"),
            date_max=("business_date", "max"),
            valid_aqi_count=("aqi", "count"),
            average_aqi=("aqi", "mean"),
            average_pm2_5=("pm2_5", "mean"),
            average_pm10=("pm10", "mean"),
            missing_records=("has_missing", "sum"),
        )
        .sort_values("city")
    )


def _build_monthly_summary(clean):
    return (
        clean.groupby(["month", "city", "source_type", "source_label"], as_index=False)
        .agg(
            record_count=("business_date", "count"),
            valid_aqi_count=("aqi", "count"),
            average_aqi=("aqi", "mean"),
            average_pm2_5=("pm2_5", "mean"),
            average_pm10=("pm10", "mean"),
            missing_records=("has_missing", "sum"),
        )
        .sort_values(["month", "city"])
    )


def _write_csv_outputs(clean, issues, city_summary, monthly_summary, output_dir):
    clean.drop(columns=["source_label", "month"]).to_csv(
        output_dir / "clean_air_quality.csv", index=False, encoding="utf-8-sig"
    )
    issues.to_csv(output_dir / "quality_issues.csv", index=False, encoding="utf-8-sig")
    city_summary.to_csv(output_dir / "city_summary.csv", index=False, encoding="utf-8-sig")
    monthly_summary.to_csv(
        output_dir / "monthly_summary.csv", index=False, encoding="utf-8-sig"
    )


def _build_metrics(clean, issues) -> dict[str, Any]:
    return {
        "record_count": len(clean),
        "city_count": int(clean["city"].nunique()),
        "date_min": clean["business_date"].min().date().isoformat(),
        "date_max": clean["business_date"].max().date().isoformat(),
        "missing_records": int(clean["has_missing"].sum()),
        "issue_count": len(issues),
        "valid_aqi_count": int(clean["aqi"].count()),
    }


def _build_charts(clean, issues, city_summary, monthly_summary, px, to_html):
    palette = {
        "北京": "#2563eb", "上海": "#0f766e", "广州": "#ea580c",
        "成都": "#7c3aed", "武汉": "#be123c",
    }
    trend = px.line(
        clean.sort_values("business_date"),
        x="business_date", y="aqi", color="city", line_dash="source_label",
        color_discrete_map=palette,
        labels={"business_date": "业务日期", "aqi": "AQI", "city": "城市", "source_label": "来源"},
        title="五城市 AQI 日趋势（按来源分段）",
    )
    trend.update_traces(connectgaps=False, line={"width": 1.8})
    trend.update_layout(height=500, margin={"l": 48, "r": 24, "t": 54, "b": 44})

    monthly = px.line(
        monthly_summary, x="month", y="average_aqi", color="city",
        line_dash="source_label", markers=True, color_discrete_map=palette,
        labels={"month": "月份", "average_aqi": "月均 AQI", "city": "城市", "source_label": "来源"},
        title="五城市月均 AQI",
    )
    monthly.update_layout(height=460, margin={"l": 48, "r": 24, "t": 54, "b": 44})
    city_average = px.bar(
        city_summary, x="city", y="average_aqi", color="city",
        color_discrete_map=palette,
        labels={"city": "城市", "average_aqi": "有效样本平均 AQI"},
        title="城市平均 AQI 对比",
    )
    city_average.update_layout(height=420, margin={"l": 48, "r": 20, "t": 54, "b": 44})

    distribution = clean[["city", "aqi"]].dropna().copy()
    distribution["AQI 区间"] = _aqi_band(distribution["aqi"])
    band_counts = distribution.groupby(["city", "AQI 区间"], observed=True).size().reset_index(name="记录数")
    aqi_bands = px.bar(
        band_counts, x="city", y="记录数", color="AQI 区间", barmode="stack",
        title="城市 AQI 数值区间分布",
    )
    aqi_bands.update_layout(height=420, margin={"l": 48, "r": 20, "t": 54, "b": 44})

    pollutant = clean.groupby("city", as_index=False)[["pm2_5", "pm10", "no2", "o3", "so2"]].mean()
    pollutant = pollutant.melt(id_vars="city", var_name="指标", value_name="平均值")
    pollutant_chart = px.bar(
        pollutant, x="city", y="平均值", color="city", facet_col="指标",
        facet_col_wrap=3, color_discrete_map=palette,
        title="主要污染物字段均值（各指标独立纵轴）",
    )
    pollutant_chart.update_yaxes(matches=None, showticklabels=True)
    pollutant_chart.update_layout(height=650, margin={"l": 48, "r": 20, "t": 70, "b": 44})

    source_counts = clean.groupby("source_label", as_index=False).size()
    source_chart = px.bar(
        source_counts, x="source_label", y="size", color="source_label",
        labels={"source_label": "Clean 来源", "size": "记录数"},
        title="Clean Record 来源构成",
    )
    source_chart.update_layout(height=420, margin={"l": 48, "r": 20, "t": 54, "b": 44})

    if issues.empty:
        quality_html = '<div class="empty-state">当前查询结果未发现质量事件。</div>'
    else:
        issue_counts = issues.groupby(["field_name", "issue_code"], as_index=False).size()
        issue_chart = px.bar(
            issue_counts, x="field_name", y="size", color="issue_code",
            labels={"field_name": "字段", "size": "事件数", "issue_code": "问题类型"},
            title="数据质量事件分布",
        )
        issue_chart.update_layout(height=420, margin={"l": 48, "r": 20, "t": 54, "b": 44})
        quality_html = to_html(issue_chart, full_html=False, include_plotlyjs=False)

    figures = (trend, monthly, city_average, aqi_bands, pollutant_chart, source_chart)
    html_blocks = [
        to_html(fig, full_html=False, include_plotlyjs=index == 0)
        for index, fig in enumerate(figures)
    ]
    return {
        "trend": html_blocks[0], "monthly": html_blocks[1],
        "city_average": html_blocks[2], "aqi_bands": html_blocks[3],
        "pollutants": html_blocks[4], "sources": html_blocks[5],
        "quality": quality_html,
    }


def _aqi_band(series):
    import pandas as pd

    return pd.cut(
        series,
        bins=[-float("inf"), 50, 100, 150, 200, 300, float("inf")],
        labels=["≤50", "51–100", "101–150", "151–200", "201–300", ">300"],
    )


def _render_dashboard(metrics: dict[str, Any], charts: dict[str, str]) -> str:
    cards = (
        ("Clean Records", f"{metrics['record_count']:,}"),
        ("城市", str(metrics["city_count"])),
        ("日期范围", f"{metrics['date_min']}<br>— {metrics['date_max']}"),
        ("有效 AQI", f"{metrics['valid_aqi_count']:,}"),
        ("含缺失记录", f"{metrics['missing_records']:,}"),
        ("质量事件", f"{metrics['issue_count']:,}"),
    )
    card_html = "".join(
        f'<article class="card"><span>{html.escape(label)}</span><strong>{value}</strong></article>'
        for label, value in cards
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><link rel="icon" href="data:,">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>空气质量 ETL Dashboard</title>
<style>
:root{{--ink:#142033;--muted:#5d6b7c;--line:#dce4ec;--panel:#fff;--bg:#f4f7fa;--accent:#176b87}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,"Microsoft YaHei",Arial,sans-serif}}
.shell{{max-width:1440px;margin:auto;padding:36px 28px 56px}} header{{padding:28px 32px;border-radius:18px;background:linear-gradient(120deg,#10283f,#176b87);color:white;box-shadow:0 12px 32px #17324d26}}
header p{{margin:8px 0 0;color:#d8eef5}} h1{{margin:0;font-size:30px}} h2{{font-size:20px;margin:0 0 10px}}
.cards{{display:grid;grid-template-columns:repeat(6,minmax(150px,1fr));gap:12px;margin:18px 0}}
.card,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:14px;box-shadow:0 4px 16px #17324d0d}}
.card{{padding:16px}} .card span{{display:block;color:var(--muted);font-size:13px;margin-bottom:8px}} .card strong{{font-size:22px}}
.grid{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}} .panel{{padding:18px;min-width:0;overflow-x:auto}} .wide{{grid-column:1/-1}}
.note{{color:var(--muted);font-size:13px;margin:0 0 8px}} .empty-state{{padding:36px;text-align:center;color:var(--muted)}}
@media(max-width:980px){{.cards{{grid-template-columns:repeat(3,1fr)}}.grid{{grid-template-columns:1fr}}.wide{{grid-column:auto}}}}
@media(max-width:560px){{.shell{{padding:16px}}.cards{{grid-template-columns:1fr 1fr}}header{{padding:22px}}.panel .js-plotly-plot{{min-width:680px}}}}
</style></head><body><main class="shell">
<header><h1>多城市空气质量 ETL Dashboard</h1><p>历史 CSV 初始化 × API 增量采集｜Raw / Clean 可追溯分析视图</p></header>
<section class="cards">{card_html}</section>
<section class="grid">
<article class="panel wide"><h2>AQI 日趋势</h2><p class="note">历史 CSV 与 API 使用独立 Trace，跨来源时间断档不会连线。</p>{charts['trend']}</article>
<article class="panel wide"><h2>月度趋势</h2>{charts['monthly']}</article>
<article class="panel"><h2>城市对比</h2>{charts['city_average']}</article>
<article class="panel"><h2>AQI 数值区间</h2>{charts['aqi_bands']}</article>
<article class="panel wide"><h2>污染物字段</h2><p class="note">缺失值不填充；各指标纵轴独立，图中不声明现有 API 的正式单位。</p>{charts['pollutants']}</article>
<article class="panel"><h2>来源构成</h2>{charts['sources']}</article>
<article class="panel"><h2>质量事件</h2>{charts['quality']}</article>
</section></main></body></html>"""


def _render_markdown(metrics: dict[str, Any], city_summary, clean) -> str:
    source_lines = "\n".join(
        f"  - {SOURCE_LABELS.get(source, source)}：{count}"
        for source, count in clean.groupby("source_type").size().items()
    )
    city_lines = "\n".join(
        f"  - {row.city}：{int(row.record_count)} 条，AQI 有效样本 {int(row.valid_aqi_count)}，含缺失记录 {int(row.missing_records)}"
        for row in city_summary.itertuples()
    )
    return (
        "# 空气质量 ETL 运行报告\n\n"
        f"- Clean Record：{metrics['record_count']}\n"
        f"- 城市数：{metrics['city_count']}\n"
        f"- 日期范围：{metrics['date_min']} 至 {metrics['date_max']}\n"
        f"- AQI 有效样本：{metrics['valid_aqi_count']}\n"
        f"- 含缺失记录：{metrics['missing_records']}\n"
        f"- 质量事件：{metrics['issue_count']}\n"
        f"- 来源构成：\n{source_lines}\n"
        f"- 城市摘要：\n{city_lines}\n\n"
        "> 缺失值未填充；均值只使用对应字段的有效样本。历史 CSV 与 API 的时间断档不按连续观测解释。\n"
    )
