# WorkBuddy Screen Matrix

```
DOC: docs/WORKBUDDY-SCREEN-MATRIX.md
STATUS: N1 W main-path evidence
DATE: 2026-07-30
TRACK: W
SCOPE: Main path only; no full-site pixel-complete claim
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
