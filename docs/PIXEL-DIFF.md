# Pico Workbench Pixel Diff

Clean-room evidence for `grok/pico-preview-librechat-p0`. The implementation keeps
Pico branding and LibreChat authentication. It uses owner direction and public
WorkBuddy screenshots only for information architecture and layout rhythm; it does
not copy closed-source code, branded assets, illustrations, or product copy.

This document records implementation and browser evidence. It is not a release
verdict and does not claim owner acceptance or exact 100% pixel parity.

## Production Baseline

- UI implementation SHA tested: `30f64a28b26198800b2bc2cb9f3d46251f532a1a`
- Production URL: `https://pico.aivia.asia`
- Desktop viewport: `1440x900`
- Mobile viewport: `390x844`
- Shell: `apps/librechat`
- Theme tested: light

## Shell Measurements

| Element | Reference target | Production measurement | Result |
| --- | --- | --- | --- |
| Expanded sidebar | 280px | 280px | Aligned |
| Main task stage | Remaining center column | 820px at 1440px viewport | Aligned |
| Result panel | 340px | 340px | Aligned |
| Workbench canvas | `#f5f5f5` | `rgb(245, 245, 245)` | Aligned |
| Home title | Compact workbench heading | 203x34px at x=589, y=104 | Aligned to current clean-room baseline |
| Mobile result rail | Degrade without crowding | Hidden at <=1024px | Aligned |
| Horizontal overflow | None | 0px at 1440 and 390 | Aligned |

The sidebar, center stage, and result panel total `280 + 820 + 340 = 1440px`
at the desktop validation viewport. Exact element-by-element `+/-2px` comparison
still requires owner-provided full-window reference captures at matching viewport
sizes.

## Screen Matrix

| Level | Route or state | Browser check | Evidence | Remaining pixel decision |
| --- | --- | --- | --- | --- |
| Primary | Login and authenticated entry | Login succeeds; authenticated shell opens | Authenticated desktop session | Owner visual review of login page |
| Primary | `/c/new` home | Three columns, scene tabs, chips, composer, workspace control | `pixel-home-final.png` | Owner reference overlay |
| Primary | Active task | Task run bar, model/status, center conversation | `pixel-result-artifact-final.png` | Owner reference overlay |
| Primary | Result files | Summary and generated file expose open/download actions | `pixel-result-artifact-final.png` | Owner reference overlay |
| Secondary | `/assistants` | List/detail workbench opens | `pixel-assistants-final.png` | Owner reference overlay |
| Secondary | `/projects` | Project list and deletion flow work | `pixel-project-workspace-final.png` | Owner reference overlay |
| Secondary | `/capability` | Expert, skill, connector tabs and details open | Three capability screenshots | Owner reference overlay |
| Secondary | `/automation` | List and create form open; temporary test item removed | Two automation screenshots | Owner reference overlay |
| Secondary | `/more` and `/more/files` | Module hub and file library open | `pixel-files-final.png` | Owner reference overlay |
| Secondary | `/workspaces` | Workspace create/select/delete flow works | `pixel-workspaces-final.png` | Owner reference overlay |
| Tertiary | Expert detail | Model preference is visible and selectable | `pixel-capability-expert-final.png` | Owner reference overlay |
| Tertiary | Skill detail | File skill recommends `pico-agent` | `pixel-capability-skill-final.png` | Owner reference overlay |
| Tertiary | Connector detail | Detail view opens; unavailable external auth remains explicit | `pixel-connector-final.png` | Owner reference overlay |
| Tertiary | Automation create | Dense workbench form opens and returns to list | `pixel-automation-create-final.png` | Owner reference overlay |
| Tertiary | Project workspace | Dynamic/plan/task/assets tabs and right configuration rail work | Two project screenshots | Owner reference overlay |
| Shell state | Collapsed sidebar | Assistant/project/capability/automation/more/workspace icons remain reachable | `pixel-sidebar-collapsed-final.png` | Owner reference overlay |

No external connector is presented as connected without real server-side
authorization. Unavailable integrations remain labelled as pending connection.

## Responsive Audit

The following eight routes were checked independently at both `1280x900` and
`390x844`:

`/c/new`, `/assistants`, `/projects`, `/capability`, `/automation`, `/more`,
`/more/files`, and `/workspaces`.

| Viewport | Route checks | Width result | Console result |
| --- | ---: | --- | --- |
| 1280x900 | 8/8 | `scrollWidth == clientWidth` on every route | 0 errors, 0 warnings |
| 390x844 | 8/8 | `scrollWidth == clientWidth` on every route | 0 errors, 0 warnings |

Mobile evidence: `mobile-home-agent.png` and `mobile-secondary-agent.png`.

## P0 Regression Evidence

Only two API-side changes were made during pixel closure, both for user-visible P0
regressions rather than business expansion:

1. Task identity now prefers the explicit Pico conversation marker, so task ledger
   state binds to the actual LibreChat conversation.
2. Streamed `pico-agent` runs now execute normal finalization, so generated files
   appear in the right result panel.

Production browser validation created `final-check.txt` through a real chat. The
task bar reached completed state and the right result panel displayed both the
reply summary and the 4-byte text artifact with open/download actions. Temporary
automation, project, and workspace records created for validation were removed.

## Screenshot Inventory

Production screenshots saved under `output/playwright/`:

- `pixel-home-final.png`
- `pixel-result-artifact-final.png`
- `pixel-sidebar-collapsed-final.png`
- `pixel-assistants-final.png`
- `pixel-project-workspace-final.png`
- `pixel-project-bound-final.png`
- `pixel-capability-expert-final.png`
- `pixel-capability-skill-final.png`
- `pixel-connector-final.png`
- `pixel-automation-list-final.png`
- `pixel-automation-create-final.png`
- `pixel-files-final.png`
- `pixel-workspaces-final.png`
- `mobile-home-agent.png`
- `mobile-secondary-agent.png`

## Owner Reference Gaps

These screens lack owner-provided, full-window WorkBuddy captures at matching
viewport sizes, so exact `+/-2px` comparison and a 100% pixel claim remain blocked:

- Login
- Assistants list/detail
- Projects list and project workspace
- Expert, skill, and connector tabs/details
- Automation list/create
- More, file library, and workspaces
- Active task and generated-file result states

The current evidence supports functional reachability, workbench visual character,
column geometry, responsive stability, and production smoke behavior. Final visual
acceptance remains with the owner.
