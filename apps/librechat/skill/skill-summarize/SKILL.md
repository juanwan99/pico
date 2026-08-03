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

Read a referenced workspace artifact when needed, extract the main points, conclusions, and action items, and optionally save the result as a workspace artifact. Do not add facts that are absent from the source.
