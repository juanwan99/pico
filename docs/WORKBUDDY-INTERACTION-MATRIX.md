# WorkBuddy Interaction Matrix

```
DOC: docs/WORKBUDDY-INTERACTION-MATRIX.md
STATUS: N3-THICK interaction coverage matrix
DATE: 2026-07-31
TRACK: W / N3合流
SCOPE: Main path + full-site primary interaction rows; no pixel-100 claim
```

| Step | Interaction | Expected result | Evidence | Result |
| --- | --- | --- | --- | --- |
| 1 | Submit from `/c/new` composer | New conversation/task opens, user prompt is visible | `output/playwright/n1-mainpath/01-home-1280.png`, `output/playwright/n1-mainpath/02-running-1280.png` | Y |
| 2 | Observe active task status | Task chrome shows model/status; no blank page during task route | `output/playwright/n1-mainpath/02-running-1280.png` | Y |
| 3 | Inspect result rail | Artifact cards appear in overview | `output/playwright/n1-mainpath/02-running-1280.png` | Y |
| 4 | Create and confirm S7 demo proposal | Banner changes from proposed to confirmed without edu write | `output/playwright/n1-mainpath/03-s7-proposed-1280.png`, `output/playwright/n1-mainpath/04-s7-confirmed-1280.png` | Y |
| 5 | Open and download artifact | Opened artifact body is `N1_MAINPATH_OK`; downloaded file saved locally | `output/playwright/n1-mainpath/download-n1-mainpath.txt` | Y |
| 6 | Create project, launch scoped task, create asset | Project route opens; task launches with project scope; result rail shows `n1-project-asset.txt` | `output/playwright/n1-mainpath/06-project-created-1280.png`, `output/playwright/n1-mainpath/07-project-task-landing-1280.png`, `output/playwright/n1-mainpath/08-project-task-result-1280.png` | Y |
| 7 | Mobile 390 task route | No horizontal overflow; core task content usable; result entry visible in captured authenticated pass | `output/playwright/n1-mainpath/09-home-390.png`, `output/playwright/n1-mainpath/10-project-task-390.png` | Y |

## Breakpoint List

No P0 main-path breakpoints were found during N1 production smoke. The only local environment limitation was workstation setup: Docker and Mongo were unavailable, so browser validation used production while local verification stayed to tests/builds.

## N3 Interaction Rows

| Area | Interaction | Expected result | Evidence | Result |
| --- | --- | --- | --- | --- |
| Capability / Skills | Open `/capability?tab=skills`, select `skill.chat`, start task | `/c/new` prefilled with Pico marker, visible Skill badge, Run snapshot resolves to `skill-chat` | `scripts/n3_skill_snapshot_smoke.py --api ...`; `output/playwright/n3-thick/capability-skills-1280.png` | Y |
| Capability / Skills | Select `skill.read`, submit | Run `token_usage.skill_snapshot.id=skill-read`; tools narrowed to `fake_edu_list_classes` | `scripts/n3_skill_snapshot_smoke.py --api ...` | Y |
| Capability / Skills | Select `skill.write_s7`, submit | Run snapshot `skill-write-s7`; existing S7 proposed change created | `scripts/n3_skill_snapshot_smoke.py --api ...` | Y |
| Automation | Create mode binding selector | Skill choices are N2 ids; copy states binding is metadata, no fake immediate run | `output/playwright/n3-thick/automation-create-1280.png` | Y |
| Automation | List refresh / toggle / delete | Calls real `/v1/automations`; errors show inline alert | Existing AutomationPage tests + production smoke | Y |
| Files | Open file library, select artifact, download | Inline artifacts preview/download; download failure shows visible warning | `output/playwright/n3-thick/files-1280.png` | Y |
| Projects | Missing project route | User sees Chinese error card and can return to project list | Code path in `ProjectWorkspace`; screenshot NO_REF | Y |
| Projects | Assets on 390px | Asset rows collapse; no forced table horizontal scroll | `output/playwright/n3-thick/project-assets-390.png` | Y |
| More | Click future connector tile | Opens connector detail with status/scope; no fake connected state | `output/playwright/n3-thick/connector-detail-1280.png` | Y |
| Spaces | Create/select/delete workspace | Uses Pico workspace API; local selected workspace cache updated | Existing WorkspaceHub implementation; screenshot `output/playwright/n3-thick/workspaces-1280.png` | Y |
| Sidebar | Collapse/expand while in task | Existing route state remains `/c/:conversationId`; no N3 code change | NO_REF; carried from N1 smoke | Backlog |
| Dark mode | Main path contrast | No N3 theme pass beyond existing dark classes | NO_REF | Backlog |

## N3 Automation

- Repeatable script: `python scripts/n3_skill_snapshot_smoke.py` for CI policy/frontmatter smoke.
- Live script: `python scripts/n3_skill_snapshot_smoke.py --api http://127.0.0.1:18765` for Run snapshot + S7 smoke.
- CI hook: `.github/workflows/ci.yml` runs the policy/frontmatter mode.
