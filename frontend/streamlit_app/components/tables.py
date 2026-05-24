"""
表格渲染輔助元件。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


def paginated_dataframe(
    items: list[dict],
    column_map: dict[str, str],
) -> None:
    """
    將 items 轉成 DataFrame 並以 column_map 重新命名後顯示。
    """
    if not items:
        st.info("無資料。")
        return
    df = pd.DataFrame(items)
    available = [c for c in column_map if c in df.columns]
    df_show = df[available].rename(columns=column_map)
    st.dataframe(df_show, use_container_width=True, hide_index=True)
