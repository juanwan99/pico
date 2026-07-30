# WorkBuddy Interaction Matrix

```
DOC: docs/WORKBUDDY-INTERACTION-MATRIX.md
STATUS: N1 W main-path evidence
DATE: 2026-07-30
TRACK: W
SCOPE: Main path only
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
