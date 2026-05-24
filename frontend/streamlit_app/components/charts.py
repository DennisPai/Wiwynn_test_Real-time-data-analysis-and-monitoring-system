"""
Plotly 圖表元件（F2 Analytics / Realtime 使用）。
"""
from __future__ import annotations

import plotly.graph_objects as go


def line_chart(
    x: list,
    y: list,
    title: str = "",
    x_label: str = "時間",
    y_label: str = "數值",
) -> go.Figure:
    """折線圖。"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name=title))
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        margin={"l": 40, "r": 20, "t": 40, "b": 40},
    )
    return fig


def bar_chart(
    categories: list[str],
    values: list[float],
    title: str = "",
) -> go.Figure:
    """長條圖。"""
    fig = go.Figure(go.Bar(x=categories, y=values))
    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 40, "b": 40},
    )
    return fig
