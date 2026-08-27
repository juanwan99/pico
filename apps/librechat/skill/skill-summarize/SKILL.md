---
name: skill-summarize
description: Summarize supplied or saved content and optionally save a grounded artifact.
allowed-tools:
  - workspace_read_file
  - structured_outline
  - workspace_write_file
  - generate_html_document
  - generate_docx_document
  - generate_pptx_document
disable-model-invocation: true
user-invocable: true
always-apply: false
---

# skill.summarize

The teacher mounted this skill. Follow their message. Do not invent a summarize workflow. Do not add facts that are absent from the source.
