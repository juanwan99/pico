---
name: skill-meeting-notes
description: Structure meeting content and optionally save the notes as an artifact.
allowed-tools:
  - structured_outline
  - workspace_write_file
  - generate_html_document
  - generate_docx_document
  - generate_pptx_document
disable-model-invocation: true
user-invocable: true
always-apply: false
---

# skill.meeting_notes

Organize the meeting content into topics, decisions, owners, and action items, then optionally save the notes as a workspace artifact. Mark an owner as unassigned when the source does not name one.
