# Agen Mini design system

Reference direction: OpenAI editorial restraint, Apple spacing and system type, Linear dark surface hierarchy. This is a working application: keep task states, model choices and logs useful rather than copying a marketing homepage.

## Foundation

- System font only. Body 15-16px / 1.6-1.8; compact metadata 11-13px; headings 29-34px at weight 500. Avoid 700+ display type.
- Light canvas white, sidebar #f8f8f9, text #202124, secondary #696b73. Dark canvas #101113, panels #191a1d, text #eeeeef, secondary #a0a3ac. Tokens live in theme.css, including furniture and studio surfaces.
- Spacing: 8 / 12 / 16 / 24 / 32px. Reading columns 760px, admin content up to 1120px. Cards 16px, fields 10px, action buttons pill shaped. Hairline borders rather than shadows; only dialogs and composer use slight elevation.
- One visually primary action per section. Secondary actions outlined; utility buttons quiet. Colour is reserved for meaningful states and characters. No decorative gradients, remote fonts or assets, UI framework, game engine or canvas loop.

## Hierarchy

Four sidebar destinations: Chat, Workspace, Koneksi, Pengaturan. Each non-chat page has labelled tabs and exactly one visible feature panel. Move original DOM nodes once at startup; never clone forms or replace their contents on tab switches. Keep drafts, scroll positions, IDs, handlers and API contracts.

Workspace: Kantor, Proyek, Aktivitas, Ide & biaya, Tim bot, Jadwal. Connections: AI & model, Akun layanan, MCP. Settings: Umum, Skill, Ingatan, Update, Diagnostik. Advanced settings use native details/summary, not a separate modal.

Tabs expose tablist/tab/tabpanel roles, aria-selected and aria-controls. Arrow keys, Home and End move focus and select a tab. Mobile tabs can scroll inside their own strip; the page must never scroll horizontally. Offscreen drawers are inert; Escape and outside click close them, and keyboard focus stays within an open drawer.

## Chat and studio

Chat uses one reading column, a compact model selector and a clearly visible composer. Keep streaming/tool status, attachments, errors, approvals and history available. The mobile model action uses a labelled check icon to leave room for the dropdowns.

Desktop studio groups the team into rooms with a separate meeting/waiting area. Mobile studio uses a simple two/three-column character stage without miniature furniture. Character silhouettes vary (round, triangle, square, cloud, asymmetric, flame), with glasses, headphones and other accessories. Names and status remain readable, and each character opens its chat. Logs live in the Activity tab. All names are text, never generated imagery.

Position characters in non-overlapping 86 x 112px slots, including queues and meetings. Layout grows with team size; never pile agents onto one waiting slot. One ResizeObserver, persistent character nodes and the existing SSE/poll are sufficient. No added per-character polling or worker.

Animations use CSS transform/opacity and pause when hidden. Preserve the motion switch and prefers-reduced-motion. Text must still communicate the true status without motion. Never fabricate work, completion or download percentages.

## Verification

Check desktop 1024/1280/1440 and mobile 320/390/430, both themes, keyboard tabs/drawer, form drafts, bot settings, history, dialog bounds and scene layout with 2/10/30 agents. Test actual API-loaded pages in the browser, not only static HTML. Distinguish preview/fixture validation from live VPS/provider/model validation. Data, tokens and models must remain untouched by visual updates.
