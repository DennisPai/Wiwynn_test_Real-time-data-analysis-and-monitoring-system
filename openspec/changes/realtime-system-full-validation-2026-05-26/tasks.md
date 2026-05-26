# Tasks — Real-time System Full Validation

## Phase 1: codebase audit
- [x] T1.1 spot check 主 repo（24 endpoints 全實裝）
- [x] T1.2 清理 3 個 stale worktrees

## Phase 2: OpenSpec + test plan
- [x] T2.1 寫 proposal.md
- [x] T2.2 寫 tasks.md
- [ ] T2.3 派 test-automator 跑 backend API 測試

## Phase 3: 實機測試

### Phase 3.A Backend API test（sub-agent）
- [ ] T3.A.1 3 角色 JWT login + /auth/me 驗 token
- [ ] T3.A.2 24 endpoint × 4 角色（含 unauth）= ~70 permission case
- [ ] T3.A.3 CRUD owner / non-owner / admin 權限矩陣
- [ ] T3.A.4 CSV import + JSON import（含 error 逐行回報）
- [ ] T3.A.5 Analytics summary / timerange / categories
- [ ] T3.A.6 Excel export 驗證 xlsx 真下載
- [ ] T3.A.7 WebSocket /ws/realtime 連線 + tick 接收
- [ ] T3.A.8 Admin settings PATCH 動態改閾值

### Phase 3.B Frontend Playwright（main session）
- [ ] T3.B.1 三角色登入 / Session / 登出
- [ ] T3.B.2 Dashboard / Data / Analytics / Realtime / Admin 頁面
- [ ] T3.B.3 WebSocket 即時圖表更新
- [ ] T3.B.4 非 Admin 隱藏 Admin 頁

## Phase 4: bug 修正閉環
- [ ] T4.1 每 bug 派 debugger 找根因
- [ ] T4.2 派 backend / frontend-engineer 修
- [ ] T4.3 push + Zeabur redeploy
- [ ] T4.4 重 test 直到全綠

## Phase 5: 雙重驗證
- [ ] T5.1 implementation-validator 對需求 35+ 條 + 5 交付物
- [ ] T5.2 修補 gap

## Phase 6: commit + push + 回報
- [ ] T6.1 commit + push
- [ ] T6.2 Discord 完成回報
