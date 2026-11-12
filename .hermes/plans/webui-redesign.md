# WebUI Redesign Plan — ObtainHub

## Phase 1 — Audit (COMPLETE)
- Read index.html (full SPA: shell, dashboard, apps list/search/check/candidates/add/sources, downloads, config, help, doctor, state, logs, about, pick/login modals, toasts)
- Read style.css (dark slate #0d1117 theme, blue #4f8cff accent, all component classes)
- Read app.js (all routes, sort, filters, modals, folder-scan flow just added)
- Read routes.rs/mod.rs (Axum routes, all preserved)

## Phase 2 — Design System (IN PROGRESS)
- Deep navy bg (#0a0e1a), surface (#131b2e), electric blue (#00d4ff) + cyan (#33ccff) accents
- Reusable CSS variables, rounded panels, subtle borders, shadows
- Keep ALL existing class names/IDs so JS + routes work unchanged

## Phase 3 — Main Interfaces
- Shell: sidebar + header modernization
- Dashboard: metric cards, recent activity
- Applications: sortable tables, badges, action menus
- Discovery: search & install
- Updates: check results
- Settings: config modernization

## Phase 4 — Integration
- cargo check passes (Rust unchanged)
- All routes/endpoints preserved
- All JS logic preserved

## Phase 5 — QA
- Build verification
- No fabricated data