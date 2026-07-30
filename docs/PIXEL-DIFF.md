# Pico Workbench Pixel Diff

Clean-room evidence for `grok/pico-preview-librechat-p0`. The implementation keeps
Pico branding and LibreChat authentication. It uses owner direction, public
WorkBuddy screenshots, and direct visual inspection of the owner's installed
WorkBuddy 5.3.5 application for information architecture and layout rhythm. It
does not inspect or copy closed-source code, branded assets, illustrations, or
product copy.

This document records implementation and browser evidence. It is not a release
verdict and does not claim owner acceptance or exact 100% pixel parity.

## Production Baseline

- UI implementation SHA tested: `83e4011f9631dae13d829b8174b8c090b36ec1fa`
- Production URL: `https://pico.aivia.asia`
- Desktop viewport: `1440x900`
- Mobile viewport: `390x844`
- Shell: `apps/librechat`
- Theme tested: light
- LibreChat rebuilt: yes, image `sha256:94131a92da3d014d7207ee096f06e8d3ace0e82761a735d3a3a7d3048c5dfd1a`

## Shell Measurements

Direct WorkBuddy measurements were taken from a maximized `1452x877` native
window on 2026-07-30. Pico production evidence uses a `1440x900` browser
viewport, so proportional column values are compared separately from vertical
window chrome.

| Element | WorkBuddy 5.3.5 reference | Previous production | Corrected implementation target |
| --- | --- | --- | --- |
| Expanded sidebar | 264px | 280px | 264px |
| Active-task center column | about 871px | 820px | 860px at 1440px |
| Active-task result panel | about 317px | 340px | 316px |
| New-task result panel | Hidden | Visible at 340px | Hidden |
| New-task composer | about 799x180px including workspace footer | 720px card plus detached controls | 797px attached card/footer |
| Active-task composer | about 798x126px | 768x148px minimum | 797x126px |
| Home title top | about y=190px including native menu chrome | y=104px | Desktop stack moved down 76px |
| Workbench canvas | Near-white main / `#f0f0f0` rail | `#f5f5f5` / `#f0f0f0` | Retained |

At the corrected browser viewport, the active-task geometry totals
`264 + 860 + 316 = 1440px`. The native WorkBuddy task view totals approximately
`264 + 871 + 317 = 1452px`.

## Native WorkBuddy Screen Audit

The following installed-app states were inspected directly without sending a
message, authorizing a connector, or modifying WorkBuddy data:

| Screen | Observed structure used for Pico |
| --- | --- |
| New task | Sidebar plus full-width main stage; centered title/scenes; 799px composer with attached workspace footer; no result rail |
| Existing task with `hello.txt` | 264px sidebar, dense conversation center, 317px browser/artifact rail, 798x126px bottom composer |
| Assistant | Minimal local-assistant chat shell with bottom composer; no marketing cards |
| Project list | Wide title/banner band, one project row, then two-row template grid |
| Expert center | Top expert/skill/connector pills, visual scene carousel, category strip, three-column expert cards |
| Skill center | Same top shell, four-column featured skills, category strip, dense four-column skill cards |
| Automation | Two-option top tab, centered empty state, three-column template grid |
| More | Anchored popover menu rather than a standalone landing page |
| My files | Title/subtitle, two tabs, compact toolbar, and table-style file list |

These observations replace the earlier assumption that a fresh task should
always show three columns and that the sidebar/result widths were 280/340px.

## Density Optimization Pass

Measured on production before and after `6b38e39`/`83e4011`. The screenshots use
the same `1440x900` desktop viewport and `390x844` mobile viewport.

| Screen | Element | Before | After | Evidence |
| --- | --- | ---: | ---: | --- |
| Home | Scene tabs top margin | 28px | 24px | `pixel-home-opt-before.png` / `pixel-home-opt.png` |
| Home | Capability chips top margin | 20px | 16px | `pixel-home-opt-before.png` / `pixel-home-opt.png` |
| Home | Composer top margin | 28px | 20px | `pixel-home-opt-before.png` / `pixel-home-opt.png` |
| Home | Landing stack height | 484.6px | 468.6px | `pixel-home-opt-before.png` / `pixel-home-opt.png` |
| Result | Overview body padding | 12px | 10px | `pixel-task-artifact-opt-before.png` / `pixel-task-artifact-opt.png` |
| Result | File card height | 54px | 50px | `pixel-task-artifact-opt-before.png` / `pixel-task-artifact-opt.png` |
| Result | File card radius / item gap | 12px / 10px | 8px / 8px | `pixel-task-artifact-opt-before.png` / `pixel-task-artifact-opt.png` |
| Result | Download control | 26x26px | 36x36px | `pixel-task-artifact-opt-before.png` / `pixel-task-artifact-opt.png` |
| Result | Open control | 44x26px | 48x36px | `pixel-task-artifact-opt-before.png` / `pixel-task-artifact-opt.png` |
| Mobile task | Result access | No reachable control | 36px control and 390px full-screen panel | `pixel-mobile-390-opt.png` / `pixel-mobile-result-opt.png` |

The three home gaps totalled 76px before and 60px after, a 16px reduction
without reducing chip or primary action sizes. The TaskRunBar and result header
remain 44px because they were already aligned.

The direct native-app audit showed that this historical tightening pass moved the
home stack in the wrong direction relative to WorkBuddy. The corrected pass keeps
the smaller internal gaps but moves the whole desktop stack down, widens the
composer, attaches its workspace footer, and removes the result rail from the
fresh-task state.

## Screen Matrix

| Level | Route or state | Browser check | Evidence | Remaining pixel decision |
| --- | --- | --- | --- | --- |
| Primary | Login and authenticated entry | Login succeeds; authenticated shell opens | Authenticated desktop session | Owner visual review of login page |
| Primary | `/c/new` home | Sidebar plus full main stage, scene tabs, chips, attached composer/workspace control | `pixel-home-opt.png` | Refresh after corrected deployment |
| Primary | Active task | Task run bar, model/status, center conversation | `pixel-task-artifact-opt.png` | Owner reference overlay |
| Primary | Result files | Summary and generated file expose open/download actions | `pixel-task-artifact-opt.png` | Owner reference overlay |
| Secondary | `/assistants` | List/detail workbench opens | `pixel-assistants-opt.png` | Owner reference overlay |
| Secondary | `/projects` | Project list and deletion flow work | `pixel-project-workspace-final.png` | Owner reference overlay |
| Secondary | `/capability` | Expert, skill, connector tabs and details open | Three capability screenshots | Owner reference overlay |
| Secondary | `/automation` | List and create form open; temporary test item removed | Two automation screenshots | Owner reference overlay |
| Secondary | More popover and `/more/files` | Anchored module menu and table-style file library open | `pixel-files-final.png` | Refresh after corrected deployment |
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

Mobile evidence: `pixel-mobile-390-opt.png` and `pixel-mobile-result-opt.png`.

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

The density pass did not change API code. Post-rebuild production validation:

- A new chat with `只回：演示OK` returned `演示OK` and reached completed state.
- A new `pico-agent` task generated `opt-proof.txt`; the result panel displayed
  the reply summary and the 8-byte file with open/download controls.
- At 390px, the collapsed result control opened the artifact panel full-screen,
  and the panel close control returned to the task without horizontal overflow.
- Eight primary/secondary routes returned HTTP 200 at both audited viewports.
  Independently authenticated desktop and mobile sessions each reported zero
  console errors and warnings.

## Screenshot Inventory

Production screenshots saved under `output/playwright/`:

- `pixel-home-opt-before.png`
- `pixel-home-opt.png`
- `pixel-task-artifact-opt-before.png`
- `pixel-task-artifact-opt.png`
- `pixel-assistants-opt.png`
- `pixel-mobile-390-opt.png`
- `pixel-mobile-result-opt.png`
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

The installed WorkBuddy application now supplies direct desktop reference for the
new-task, active-task, assistant, project-list, expert, skill, automation, more,
and file-library states. Exact `+/-2px` comparison and a 100% pixel claim remain
blocked for surfaces that do not have like-for-like native/web states or have not
yet been captured at matching dimensions:

- Login
- Mobile 390 layout
- Project workspace detail
- Connector detail and authorization states
- Workspace management

The current evidence supports functional reachability, workbench visual character,
column geometry, responsive stability, and production smoke behavior. Final visual
acceptance remains with the owner.
