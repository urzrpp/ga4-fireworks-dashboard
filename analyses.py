"""4대 분석: 프로모션 성과 / 이벤트 소스 상세 / 유입경로 / 퍼널"""

from __future__ import annotations

import pandas as pd
from google.analytics.data_v1beta.types import (
    FilterExpression,
    Filter,
    OrderBy,
)

import config
from ga4_client import run_report, run_realtime_report


def campaign_performance() -> pd.DataFrame:
    """프로모션/캠페인 성과: 캠페인별 세션, 전환, 매출, 거래 수"""
    dim_filter = None
    if config.PROMO_NAME_FILTER:
        dim_filter = FilterExpression(
            filter=Filter(
                field_name="sessionCampaignName",
                string_filter=Filter.StringFilter(
                    value=config.PROMO_NAME_FILTER,
                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                    case_sensitive=False,
                ),
            )
        )

    df = run_report(
        dimensions=["sessionCampaignName", "sessionSourceMedium", "sessionDefaultChannelGroup"],
        metrics=["sessions", "conversions", "totalRevenue", "transactions", "engagementRate"],
        dimension_filter=dim_filter,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
    )
    if not df.empty:
        df = df[df["sessionCampaignName"] != "(not set)"]
    return df


def event_source_detail() -> pd.DataFrame:
    """이벤트 소스 상세: 이벤트명 x 소스/매체 x 채널그룹 별 활성 사용자 수 기준"""
    df = run_report(
        dimensions=["eventName", "sessionSourceMedium", "sessionDefaultChannelGroup"],
        metrics=["activeUsers", "eventCount", "eventValue"],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="activeUsers"), desc=True)],
    )
    return df


def acquisition_channels() -> pd.DataFrame:
    """유입경로: 채널그룹 / 소스 / 매체별 활성 사용자 수 기준"""
    df = run_report(
        dimensions=["sessionDefaultChannelGroup", "sessionSource", "sessionMedium"],
        metrics=["activeUsers", "newUsers", "engagedSessions", "conversions", "totalRevenue"],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="activeUsers"), desc=True)],
    )
    return df


def funnel_analysis() -> pd.DataFrame:
    """
    퍼널 분석: config.FUNNEL_STEPS 순서대로 각 이벤트를 발생시킨 고유 사용자 수를 집계하고
    단계별 전환율 / 이탈률을 계산.

    주의: GA4 Data API는 '엄격한 순서'를 강제하는 네이티브 퍼널 엔드포인트가 없어서
    이 함수는 각 단계 이벤트를 발생시킨 사용자 수의 근사치입니다.
    사용자별 이벤트 순서를 엄격히 강제한 정확한 퍼널이 필요하면 BigQuery Export 연동을 권장합니다.
    """
    rows = []
    prev_users = None
    for step in config.FUNNEL_STEPS:
        dim_filter = FilterExpression(
            filter=Filter(
                field_name="eventName",
                string_filter=Filter.StringFilter(
                    value=step,
                    match_type=Filter.StringFilter.MatchType.EXACT,
                ),
            )
        )
        df = run_report(
            dimensions=["eventName"],
            metrics=["activeUsers", "eventCount"],
            dimension_filter=dim_filter,
        )
        users = int(df["activeUsers"].iloc[0]) if not df.empty else 0
        events = int(df["eventCount"].iloc[0]) if not df.empty else 0

        step_conv = (users / prev_users * 100) if prev_users else 100.0
        drop_off = 100.0 - step_conv if prev_users else 0.0

        rows.append(
            {
                "step": step,
                "users": users,
                "event_count": events,
                "step_conversion_rate_%": round(step_conv, 2),
                "drop_off_%": round(drop_off, 2),
            }
        )
        prev_users = users if users else prev_users

    result = pd.DataFrame(rows)
    if not result.empty and result["users"].iloc[0]:
        first = result["users"].iloc[0]
        result["overall_conversion_from_start_%"] = round(result["users"] / first * 100, 2)
    return result


def find_complete_events(date_start: str | None = None, date_end: str | None = None) -> list[str]:
    """이벤트명에 'complete'가 포함된 이벤트를 자동 탐지"""
    if config.COMPLETE_EVENTS:
        return config.COMPLETE_EVENTS
    df = run_report(
        dimensions=["eventName"],
        metrics=["eventCount"],
        date_start=date_start,
        date_end=date_end,
    )
    if df.empty:
        return []
    return sorted(df[df["eventName"].str.contains("complete", case=False)]["eventName"].tolist())


def channel_conversion_funnel(date_start: str | None = None, date_end: str | None = None) -> pd.DataFrame:
    """
    채널별 인증 전환율 + 최종 완료율 비교.

    session_start(진입) -> auth_form_submit(인증) -> complete 계열 이벤트(완료) 순으로
    채널(sessionDefaultChannelGroup)별 활성 사용자 수를 비교하고 단계별 전환율을 계산.
    """
    date_start = date_start or config.CAMPAIGN_START
    date_end = date_end or config.CAMPAIGN_END

    complete_events = find_complete_events(date_start, date_end)
    target_events = [config.FUNNEL_ENTRY_EVENT, config.AUTH_EVENT] + complete_events

    dim_filter = FilterExpression(
        filter=Filter(
            field_name="eventName",
            in_list_filter=Filter.InListFilter(values=target_events),
        )
    )
    df = run_report(
        dimensions=["sessionDefaultChannelGroup", "eventName"],
        metrics=["activeUsers"],
        dimension_filter=dim_filter,
        date_start=date_start,
        date_end=date_end,
    )
    if df.empty:
        return df

    pivot = df.pivot_table(
        index="sessionDefaultChannelGroup",
        columns="eventName",
        values="activeUsers",
        fill_value=0,
        aggfunc="sum",
    ).reset_index()

    entry_col = config.FUNNEL_ENTRY_EVENT
    auth_col = config.AUTH_EVENT
    if entry_col not in pivot.columns:
        pivot[entry_col] = 0
    if auth_col not in pivot.columns:
        pivot[auth_col] = 0

    pivot["auth_conversion_rate_%"] = pivot.apply(
        lambda r: round(r[auth_col] / r[entry_col] * 100, 2) if r[entry_col] else 0.0, axis=1
    )

    for ev in complete_events:
        if ev not in pivot.columns:
            pivot[ev] = 0
        pivot[f"{ev}_rate_from_entry_%"] = pivot.apply(
            lambda r: round(r[ev] / r[entry_col] * 100, 2) if r[entry_col] else 0.0, axis=1
        )
        pivot[f"{ev}_rate_from_auth_%"] = pivot.apply(
            lambda r: round(r[ev] / r[auth_col] * 100, 2) if r[auth_col] else 0.0, axis=1
        )

    pivot = pivot.sort_values(entry_col, ascending=False)
    return pivot


def daily_progress(date_start: str | None = None, date_end: str | None = None) -> tuple[pd.DataFrame, dict]:
    """
    일자별 활성 사용자 추이 + 목표(TARGET_ACTIVE_USERS) 대비 진척 현황.

    반환: (일자별 DataFrame, 요약 dict)
    """
    date_start = date_start or config.CAMPAIGN_START
    date_end = date_end or config.CAMPAIGN_END

    daily = run_report(
        dimensions=["date"],
        metrics=["activeUsers", "eventCount", "conversions"],
        date_start=date_start,
        date_end=date_end,
    )
    if not daily.empty:
        daily["date"] = pd.to_datetime(daily["date"], format="%Y%m%d")
        daily = daily.sort_values("date").reset_index(drop=True)
        daily["cumulative_daily_sum"] = daily["activeUsers"].cumsum()

    # 기간 전체 고유 활성 사용자 수 (일자별 합산과 달리 중복 방문자를 제거한 실제 값)
    total_df = run_report(
        dimensions=[],
        metrics=["activeUsers"],
        date_start=date_start,
        date_end=date_end,
    )
    total_unique_active_users = int(total_df["activeUsers"].iloc[0]) if not total_df.empty else 0

    goal = config.TARGET_ACTIVE_USERS
    progress_pct = round(total_unique_active_users / goal * 100, 2) if goal else 0.0

    elapsed_days = len(daily) if not daily.empty else 0
    avg_daily = round(total_unique_active_users / elapsed_days, 1) if elapsed_days else 0.0

    campaign_start_dt = pd.to_datetime(config.CAMPAIGN_START)
    campaign_end_dt = pd.to_datetime(config.CAMPAIGN_END)
    total_campaign_days = (campaign_end_dt - campaign_start_dt).days + 1
    remaining_days = max(total_campaign_days - elapsed_days, 0)
    projected_total = round(total_unique_active_users + avg_daily * remaining_days, 0)

    summary = {
        "date_start": date_start,
        "date_end": date_end,
        "elapsed_days": elapsed_days,
        "total_campaign_days": total_campaign_days,
        "remaining_days": remaining_days,
        "total_unique_active_users": total_unique_active_users,
        "target_active_users": goal,
        "progress_pct": progress_pct,
        "avg_daily_active_users": avg_daily,
        "projected_total_by_campaign_end": projected_total,
        "projected_vs_target_pct": round(projected_total / goal * 100, 2) if goal else 0.0,
    }
    return daily, summary


def source_conversion_funnel(
    date_start: str | None = None,
    date_end: str | None = None,
    chart_top_n: int = 7,
    table_top_n: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    유입 소스(수동 소스/매체, sessionSourceMedium)별 진입→인증→완료 전환 데이터.

    GA4 자동 채널 그룹(sessionDefaultChannelGroup)이 아니라 실제 소스/매체 단위로
    집계한다는 점이 channel_conversion_funnel()과 다른 점.

    반환: (chart_rows, table_rows) - 둘 다 상위 N개 소스 + "기타" 합계 행 포함.
    chart_rows 는 카테고리 컬러 슬롯(8개) 예산에 맞춰 chart_top_n(기본 7)+기타,
    table_rows 는 더 상세하게 table_top_n(기본 10)+기타 로 자른다.
    """
    date_start = date_start or config.CAMPAIGN_START
    date_end = date_end or config.CAMPAIGN_END

    dim_filter = FilterExpression(
        filter=Filter(
            field_name="eventName",
            in_list_filter=Filter.InListFilter(
                values=["session_start", "auth_form_submit", "fireworks_event_complete"]
            ),
        )
    )
    df = run_report(
        dimensions=["sessionSourceMedium", "eventName"],
        metrics=["activeUsers"],
        dimension_filter=dim_filter,
        date_start=date_start,
        date_end=date_end,
    )
    if df.empty:
        empty = pd.DataFrame(
            columns=[
                "sessionSourceMedium",
                "auth_form_submit",
                "fireworks_event_complete",
                "session_start",
                "auth_conversion_rate_%",
                "complete_rate_from_entry_%",
            ]
        )
        return empty, empty

    piv = df.pivot_table(
        index="sessionSourceMedium",
        columns="eventName",
        values="activeUsers",
        fill_value=0,
        aggfunc="sum",
    ).reset_index()
    for col in ("session_start", "auth_form_submit", "fireworks_event_complete"):
        if col not in piv.columns:
            piv[col] = 0
    piv = piv.sort_values("session_start", ascending=False).reset_index(drop=True)

    def _with_other(top_n: int, other_label: str) -> pd.DataFrame:
        top = piv.head(top_n).copy()
        rest = piv.iloc[top_n:]
        other = pd.DataFrame(
            [
                {
                    "sessionSourceMedium": other_label,
                    "auth_form_submit": rest["auth_form_submit"].sum(),
                    "fireworks_event_complete": rest["fireworks_event_complete"].sum(),
                    "session_start": rest["session_start"].sum(),
                }
            ]
        )
        out = pd.concat([top, other], ignore_index=True) if len(rest) else top
        out["auth_conversion_rate_%"] = (
            out["auth_form_submit"] / out["session_start"] * 100
        ).round(2).fillna(0.0)
        out["complete_rate_from_entry_%"] = (
            out["fireworks_event_complete"] / out["session_start"] * 100
        ).round(2).fillna(0.0)
        return out[
            [
                "sessionSourceMedium",
                "auth_form_submit",
                "fireworks_event_complete",
                "session_start",
                "auth_conversion_rate_%",
                "complete_rate_from_entry_%",
            ]
        ]

    chart_rows = _with_other(chart_top_n, "기타")
    table_rows = _with_other(table_top_n, "기타(소규모 소스 합계)")
    return chart_rows, table_rows


def realtime_snapshot() -> pd.DataFrame:
    """실시간(최근 ~30분) 이벤트별 발생 건수 스냅샷"""
    return run_realtime_report(
        dimensions=["eventName"],
        metrics=["eventCount"],
    )


def realtime_active_users() -> int:
    """실시간(최근 ~30분) 전체 활성 사용자 수"""
    df = run_realtime_report(dimensions=[], metrics=["activeUsers"])
    return int(df["activeUsers"].iloc[0]) if not df.empty else 0
