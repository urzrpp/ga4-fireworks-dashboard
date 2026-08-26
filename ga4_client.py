"""GA4 Data API 호출 공통 헬퍼"""

from __future__ import annotations

import os
import pandas as pd
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    RunRealtimeReportRequest,
    DateRange,
    Dimension,
    Metric,
    FilterExpression,
    Filter,
    OrderBy,
)

import config


def get_client() -> BetaAnalyticsDataClient:
    if os.path.exists(config.CREDENTIALS_FILE):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config.CREDENTIALS_FILE
    return BetaAnalyticsDataClient()


def _property_path() -> str:
    return f"properties/{config.GA4_PROPERTY_ID}"


def run_report(
    dimensions: list[str],
    metrics: list[str],
    dimension_filter: FilterExpression | None = None,
    order_bys: list[OrderBy] | None = None,
    limit: int = 100000,
    date_start: str | None = None,
    date_end: str | None = None,
) -> pd.DataFrame:
    """GA4 표준 리포트를 실행하고 DataFrame으로 반환"""
    client = get_client()
    request = RunReportRequest(
        property=_property_path(),
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[
            DateRange(
                start_date=date_start or config.DATE_RANGE_START,
                end_date=date_end or config.DATE_RANGE_END,
            )
        ],
        dimension_filter=dimension_filter,
        order_bys=order_bys or [],
        limit=limit,
    )
    response = client.run_report(request)

    rows = []
    for row in response.rows:
        record = {}
        for i, dim in enumerate(dimensions):
            record[dim] = row.dimension_values[i].value
        for i, met in enumerate(metrics):
            val = row.metric_values[i].value
            try:
                val = float(val) if "." in val else int(val)
            except ValueError:
                pass
            record[met] = val
        rows.append(record)

    return pd.DataFrame(rows)


def run_realtime_report(dimensions: list[str], metrics: list[str], limit: int = 1000) -> pd.DataFrame:
    """최근 ~30분 실시간 리포트를 실행하고 DataFrame으로 반환"""
    client = get_client()
    request = RunRealtimeReportRequest(
        property=_property_path(),
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        limit=limit,
    )
    response = client.run_realtime_report(request)

    rows = []
    for row in response.rows:
        record = {}
        for i, dim in enumerate(dimensions):
            record[dim] = row.dimension_values[i].value
        for i, met in enumerate(metrics):
            val = row.metric_values[i].value
            try:
                val = float(val) if "." in val else int(val)
            except ValueError:
                pass
            record[met] = val
        rows.append(record)

    return pd.DataFrame(rows)
