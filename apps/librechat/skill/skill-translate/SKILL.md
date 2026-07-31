---
name: skill-translate
description: Translate supplied or saved content and optionally save the translation.
allowed-tools:
  - workspace_read_file
  - workspace_write_file
disable-model-invocation: true
user-invocable: true
always-apply: false
---

# skill.translate

Read a referenced workspace artifact when needed, translate faithfully while preserving formatting, proper nouns, and tone, and optionally save the translation as a workspace artifact. Mark uncertain terminology instead of inventing a confident translation.
