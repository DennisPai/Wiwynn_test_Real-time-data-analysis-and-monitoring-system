# sample_data.csv 說明

## 用途
本 CSV 是「資料管理軌」（data_records 表）的示範匯入資料 — 模擬使用者補登或從外部 sensor 匯出的歷史監控資料。

## Schema（Long Format）
| 欄位 | 型別 | 說明 |
|---|---|---|
| title | str | 資料記錄標題（如「室內溫度（°C）」） |
| value | float | 數值 |
| category | str | 監控指標分類，須為以下 5 種之一：temperature / humidity / pressure / voltage / cpu_usage（**與即時監控軌共用**） |
| recorded_at | ISO8601 | 紀錄時間（UTC，建議帶 Z 後綴） |

## 與即時監控軌的關係
- **共用 5 metric category** → 在分析報表頁可用 source toggle（兩者 / 僅即時 / 僅錄入）跨軌比較
- 雙軌設計詳見 [README 「資料雙軌設計」節](../README.md#資料雙軌設計)

## 匯入方法
1. 登入後到「資料管理」頁
2. 在批量匯入 expander 上傳本檔
3. 切到「分析報表」頁切 source toggle 看跨軌統計
