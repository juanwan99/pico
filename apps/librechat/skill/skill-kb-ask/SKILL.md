---
name: skill-kb-ask
description: Ask questions against uploaded school materials. Always search first.
allowed-tools:
  - kb_search
  - workspace_list_files
  - workspace_read_file
disable-model-invocation: true
user-invocable: true
always-apply: false
---

# skill.kb_ask

Answer using materials already in the membership Artifact ledger. Call `kb_search` first; cite `artifact_id` and excerpts. If nothing matches, say so honestly (do not invent content).
