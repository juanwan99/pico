## Goal
<!-- Product outcome; this authorizes same-scope merge + stage-A deploy intent under OneFlow -->

## OneFlow
- [ ] One writer · one branch · one PR
- [ ] Risk: 绿 / 黄 / 红 （见 docs/WORKFLOW.md）
- [ ] Paths in scope:
- [ ] Forbidden paths avoided (edu-cloud, old shells, PROXY=1)

## CANDIDATE（push 后填）
- SHA: `<!-- 40-char -->`
- CI: pending / success / failure
- Review (黄/红): pending / PASS / REVISE / BLOCKED @SHA
- UI/prod smoke (if user-visible): pending / PASS · evidence:

## Evidence map
| Acceptance item | Evidence |
|-----------------|----------|
| | pytest / Actions / smoke |

## BLOCKED
- none /

## Deploy (after MERGED · stage A)
- [ ] main pull on target host
- [ ] rebuild api / librechat if needed
- [ ] `health.git_sha` matches
- [ ] `## DEPLOYED` comment posted

## Refs
- docs/ONEFLOW.md · docs/WORKFLOW.md · docs/MASTER-PLAN.md
