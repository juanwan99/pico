# WorkBuddy Screen Matrix

```
DOC: docs/WORKBUDDY-SCREEN-MATRIX.md
STATUS: N3-THICK screen coverage matrix
DATE: 2026-07-31
TRACK: W / N3合流
SCOPE: Full-site route/status coverage; main path implementation 100%; other rows may be NO_REF/backlog
```

## N1 Main Path Rows

| Step | Entry | Route / state | Reference | Pico evidence | Pixel / layout result | State coverage | Done |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Home task start | `/c/new` | WorkBuddy native home reference exists; exact overlay not in this sprint | `output/playwright/n1-mainpath/01-home-1280.png`, `output/playwright/n1-mainpath/09-home-390.png` | NO_REF for exact pixel; no desktop or 390 horizontal overflow observed | empty / ready | Y |
| 2 | Running task state | `/c/:conversationId` after submit | WorkBuddy active task reference exists; exact overlay not in this sprint | `output/playwright/n1-mainpath/02-running-1280.png` | Run completed quickly; active task chrome and status bar visible | running tail / completed | Y |
| 3 | Result rail artifact preview | `/c/da916b3e-5d61-45a4-b510-0d2003dcaeea` | WorkBuddy active task with result rail reference exists | `output/playwright/n1-mainpath/02-running-1280.png` | Right rail present with overview cards; no 404/white screen | artifact list / preview | Y |
| 4 | S7 confirmation banner | Same task, demo proposal | Pico S7 product rule; WorkBuddy pixel exactness not claimed | `output/playwright/n1-mainpath/03-s7-proposed-1280.png`, `output/playwright/n1-mainpath/04-s7-confirmed-1280.png` | Banner visible; proposed and confirmed states visible | proposed / confirmed | Y |
| 5 | Open, download, history/files | Result rail and global files | WorkBuddy file-library reference exists; exact overlay not in this sprint | `output/playwright/n1-mainpath/download-n1-mainpath.txt`, `output/playwright/n1-mainpath/02-running-1280.png` | Open returned `N1_MAINPATH_OK`; download saved `n1-mainpath.txt` | open / download / file entry | Y |
| 6 | Project-scoped task and asset | `/projects/:projectId` -> `/c/new?projectId=...` -> `/c/:conversationId` | WorkBuddy project workspace reference exists; exact overlay not in this sprint | `output/playwright/n1-mainpath/05-projects-1280.png`, `output/playwright/n1-mainpath/06-project-created-1280.png`, `output/playwright/n1-mainpath/07-project-task-landing-1280.png`, `output/playwright/n1-mainpath/08-project-task-result-1280.png`, `output/playwright/n1-mainpath/10-project-task-390.png` | Project page, scoped landing, and result rail all reachable | project empty / project task / project asset | Y |

## Notes

- Evidence was collected on production `https://pico.aivia.asia` with the demo account.
- The N1 run found no main-path 404, white screen, fake button, or blocking refresh flash.
- Exact full-site pixel parity remains out of scope for N1. Rows above use `NO_REF` where no like-for-like overlay was produced.

## N3 Full-Site Route Rows

| Area | Entry | Route / state | Reference | Pico evidence | Layout / truth result | State coverage | Done |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Chat | New task | `/c/new` | WorkBuddy home task entry; exact overlay not claimed | `output/playwright/n3-thick/home-1280.png`, `output/playwright/n3-thick/home-390.png` | Main path stays Y; pending Skill badge visible after Capability Hub selection | empty / prefilled / ready | Y |
| Chat | Existing task | `/c/:conversationId` | WorkBuddy active task reference | `output/playwright/n1-mainpath/02-running-1280.png` | Task chrome + result rail reachable; no 404/white screen regression | running / result / artifact | Y |
| Assistants | Assistant list/detail | `/assistants` | WorkBuddy assistant hub concept; exact pixel NO_REF | `output/playwright/n3-thick/assistants-1280.png` | Real secondary page; selecting an assistant preps `/c/new`; no fake terminal action | list / detail / summon | Y |
| Projects | Project list | `/projects` | WorkBuddy project list concept; exact pixel NO_REF | `output/playwright/n3-thick/projects-1280.png` | Search/sort/create entry visible; empty state has real create action | loading / empty / list / delete confirm | Y |
| Projects | Create project | `/projects?new=1` | NO_REF | `output/playwright/n3-thick/project-create-1280.png` | Native create dialog; submit creates real LibreChat project | dialog / validation / created | Y |
| Projects | Project workspace | `/projects/:projectId` | WorkBuddy workspace concept | `output/playwright/n1-mainpath/06-project-created-1280.png`, `output/playwright/n3-thick/project-assets-390.png` | Dynamic/plan/tasks/assets tabs reachable; narrow asset rows collapse to one column | tabs / empty / asset preview | Y |
| Projects | Missing project | `/projects/:projectId` not found | NO_REF | NO_REF | N3 adds explicit Chinese error card + return action instead of bare blank text | not found / no access | Y |
| Capability | Capability hub | `/capability` | WorkBuddy capability hub concept; exact pixel NO_REF | `output/playwright/n3-thick/capability-skills-1280.png` | Experts/Skills/Connectors tabs reachable; Skills list is the N2 three-skill set | experts / skills / connectors | Y |
| Capability | Skill detail/start | `/capability?tab=skills` | LibreChat Skills is unique catalog source; Pico snapshot is ledger-only | `output/playwright/n3-thick/skill-write-s7-detail-1280.png` | `skill-chat/read/write-s7` selectable; click preloads Pico marker and model preference | list / detail / prefill | Y |
| Capability | Connector detail | `/capability/connectors/:connectorId` | NO_REF | `output/playwright/n3-thick/connector-detail-1280.png` | Ready connector can be used; future connectors save draft only and label authorization boundary | ready / draft / disabled boundary | Y |
| Automation | Automation list | `/automation` | WorkBuddy automation list concept; exact pixel NO_REF | `output/playwright/n3-thick/automation-list-1280.png` | Real `/v1/automations` list/toggle/delete; no fake Run button | loading / empty / list / error | Y |
| Automation | Create automation | `/automation` create mode | NO_REF | `output/playwright/n3-thick/automation-create-1280.png` | Schedule/model/workspace/permission/binding saved; N3 text clarifies Skill binding is metadata | create / validation / save error | Y |
| More | More hub | `/more` | WorkBuddy more/library concept; exact pixel NO_REF | `output/playwright/n3-thick/more-1280.png` | Tiles route to real file/capability/connector detail surfaces; future items show authorization boundary | ready / future connector | Y |
| More | File library | `/more/files` | WorkBuddy file library concept | `output/playwright/n3-thick/files-1280.png` | Real Pico artifact ledger; N3 download failures surface as visible warnings | loading / empty / preview / download error | Y |
| Spaces | Workspace hub | `/workspaces` | WorkBuddy space selector concept; exact pixel NO_REF | `output/playwright/n3-thick/workspaces-1280.png` | Real Pico workspace API plus local selector cache; create/delete have visible states | loading / list / create / delete | Y |
| Skills | LibreChat Skills index | `/skills`, `/skills/manage` | Upstream LibreChat Skills UI | `output/playwright/n3-thick/lc-skills-1280.png` | Unique product catalog remains LibreChat; no public Pico `/v1/skills` browser added | list / manage | Y |
| Skills | LibreChat Skill create/edit | `/skills/new`, `/skills/:skillId/edit` | Upstream LibreChat Skills UI | NO_REF | Route exists via upstream lazy SkillsView; detailed parity backlog outside N3 | create / edit | Backlog |
| Agents | Agent marketplace | `/agents`, `/agents/:category` | Upstream LibreChat marketplace | NO_REF | Route exists; not pixel audited in N3 | list / category | Backlog |
| Prompts | Prompt editor | `/prompts/new`, `/prompts/:promptId` | Upstream LibreChat prompts | NO_REF | Route exists; not in WorkBuddy main scope | create / edit | Backlog |
| Search | Search | `/search` | Upstream LibreChat search | NO_REF | Route exists; not in WorkBuddy main scope | query / results | Backlog |
| Auth | Login | `/login` | Auth shell | `output/playwright/n3-thick/login-1280.png` | Login renders and auth errors remain inline, not white screen | ready / error | Y |

## N3 Coverage Summary

- 一级入口行覆盖：`/c/new`、助理、项目、能力中心、自动化、更多、空间、Skills、Agents、Prompts、Search、Auth = 100% 有行。
- 主路径实现率：N1 六步保持 100%。
- N3 二三级诚实：实现可证的页面标 `Y`；未深测上游非主路径标 `Backlog`；无精确参考处标 `NO_REF`。
- 本矩阵不是像素 100% 声明。
