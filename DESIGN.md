# Agen Mini design rules

Use the system font, neutral surfaces, one primary action per panel, and concise Indonesian labels. Keep desktop reading areas at 760-1040px. Spacing follows 8/16/24px; cards use 14-16px radii and a subtle border. Reserve color for status and characters. Avoid decorative gradients and heavy animation.

Below 760px: sidebar drawer, single-column forms/model cards, two-column office, 44px touch controls, 16px input text, and no horizontal page scrolling. Preserve labels, loading/error/empty states, keyboard focus, contrast, and reduced motion. SVG characters are served locally; no web font/CDN/game engine.

Status comes from actual task/trace records. A failed task must not show success. Logs are owner-authenticated. Every new component should follow these rules and be checked at desktop and mobile widths.


Navigation: only Chat, Workspace, Koneksi and Pengaturan in the main sidebar. Secondary sections stay in compact tab bars. Runtime readiness must reflect live server/model identity; saved preference is not readiness. Downloads use real byte progress, a lightweight CSS spinner and a reduced-motion fallback, with distinct verification/loading/failure states. Each bot exposes the shared provider engine and its own model choice.

Mobile: two-column engine choices, safe-area padding, wrapping status/toasts and scrollable dialogs bounded by 100dvh. Drawers close by tapping outside or Escape. Validate page and modal widths at 320, 390 and 430px.
