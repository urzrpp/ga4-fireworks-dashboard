"""
대시보드 Artifact에 그대로 꽂아넣을 DATA JSON을 GA4에서 새로 뽑는 스크립트.

사용법:
    python3 refresh_pipeline.py > output/live_data.json
    (stderr 로 사람이 읽을 요약도 같이 출력)

이 스크립트는 파일을 발행(publish)하지 않는다 — 그건 Claude(Artifact 툴)만 할 수 있음.
이 스크립트는 "최신 DATA JSON 한 덩어리"만 만들어준다.
"""

from __future__ import annotations

import json
import sys

import pandas as pd

import config
from analyses import (
    acquisition_channels,
    event_source_detail,
    realtime_snapshot,
    daily_progress,
    funnel_analysis,
    source_conversion_funnel,
)


def df_records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records"))


def main():
    acquisition = acquisition_channels()

    events = event_source_detail()  # 전체 (~800행), activeUsers 내림차순 정렬됨
    event_top20 = events.head(20)
    event_agg10 = (
        events.groupby("eventName", as_index=False)["activeUsers"]
        .sum()
        .sort_values("activeUsers", ascending=False)
        .head(10)
    )

    realtime = realtime_snapshot()

    daily_df, summary = daily_progress()
    daily_df = daily_df.copy()
    daily_df["date"] = daily_df["date"].dt.strftime("%Y-%m-%d")

    funnel = funnel_analysis()

    source_chart, source_table = source_conversion_funnel()

    data = {
        "acquisition": df_records(acquisition),
        "eventTop20": df_records(event_top20),
        "eventAgg10": df_records(event_agg10),
        "realtime": df_records(realtime),
        "daily": df_records(daily_df),
        "summary": summary,
        "funnel": df_records(funnel),
        "sourceChart": df_records(source_chart),
        "sourceTable": df_records(source_table),
    }

    print(json.dumps(data, ensure_ascii=False))

    # 사람이 눈으로 확인할 요약은 stderr로 (stdout은 JSON 전용)
    print(
        f"[refresh] active={summary['total_unique_active_users']:,} "
        f"target={summary['target_active_users']:,} "
        f"progress={summary['progress_pct']}% "
        f"projected={summary['projected_vs_target_pct']}%",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
