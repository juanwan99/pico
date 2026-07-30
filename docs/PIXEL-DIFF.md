# Pico Workbench Pixel Diff

Clean-room baseline for `grok/pico-preview-librechat-p0`. Reference is owner-provided direction plus public WorkBuddy workbench screenshots for layout rhythm only; no closed-source assets or copied copy are used.

| Screen | Element | Reference | Current before | Fixed in this pass |
| --- | --- | --- | --- | --- |
| Home / empty task | Left rail width | 280px expanded rail | 263px hard-coded at runtime | Yes: `UnifiedSidebar` now uses `sidebarWidth`, default/min 280px |
| Home / empty task | Right result rail | 340px visible on desktop | Hidden for landing/new task | Yes: `ResultPanel` is default visible outside search |
| Home / empty task | Result rail mobile behavior | Desktop rail, mobile degrade | Would crowd if enabled | Yes: `.pico-result-panel` hidden at <=1024px |
| Home / empty task | Shell background | `#f5f5f5` workbench canvas | `#f5f5f5` | Already aligned |
| Home / empty task | Result rail width | 340px | 340px token/class | Already aligned |
| Result browser view | Refresh interaction | Clickable, non-crashing | `browserKey` state missing | Yes: state added |

## Production Measurement

Measured before this pass on `https://pico.aivia.asia/c/new`, viewport `1920x911`, origin `6bd65e78aea9d43a997203f5224557242336124c`:

| Element | Measured |
| --- | --- |
| Sidebar | x=0, width=263 |
| Main stage | x=263, width=1657 |
| Home title | x=990, y=104, width=203, height=34 |
| Landing stack | x=747, y=24, width=690, height=485 |
| Composer textarea | x=788, y=323, width=608, height=65 |
| Body background | `rgb(245, 245, 245)` |

Measured after this pass on `https://pico.aivia.asia/c/new`, viewport `1440x900`, origin `94741a810fa78378c934527d4852e083977bab24`:

| Element | Measured |
| --- | --- |
| Sidebar | x=0, width=280 |
| Main stage | x=280, width=820 |
| Result panel | x=1100, width=340 |
| Home title | x=589, y=104, width=203, height=34 |
| Body background | `rgb(245, 245, 245)` |
| Mobile 390 | no horizontal overflow; result rail hidden |

## Validation Screenshots

Saved locally during production validation:

- `pixel-home.png`
- `pixel-task.png`
- `pixel-task-done.png`
- `pixel-result-files.png`
- `pixel-assistants.png`
- `pixel-capability.png`
- `pixel-automation.png`
- `pixel-more.png`
- `pixel-project.png`
- `pixel-workspaces.png`
- `pixel-mobile-390.png`

## Screenshot Gaps

Exact ±2px claims still need owner full-window WorkBuddy screenshots for these screens:

- Assistants list/detail
- Projects list and project workspace
- Capability tabs and connector detail
- Automation list/create
- More / files / workspaces
