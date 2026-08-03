---
name: skill-quiz-draft
description: Draft a structured quiz from supplied or saved material and save the draft.
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

# skill.quiz_draft

Read a referenced workspace artifact when needed, create draft questions with answers and concise explanations, and optionally save the draft as a workspace artifact. Remind the user to review it before publishing.
