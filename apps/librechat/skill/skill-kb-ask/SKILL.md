---
name: skill-kb-ask
description: Answer from school materials when the teacher asks about them. Being listed does not mean you must call.
allowed-tools:
  - kb_search
  - workspace_list_files
  - workspace_read_file
disable-model-invocation: true
user-invocable: true
always-apply: false
---

# skill.kb_ask

When the teacher asks about school materials, call `kb_search` and cite titles plus excerpts. If `honest_miss=true`, say so honestly (do not invent content). Pico chat uploads are not the school library. Being listed does not mean you must call.
