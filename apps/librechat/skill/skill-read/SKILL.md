---
name: skill-read
description: Read workspace artifacts or optional demo school data without writing.
allowed-tools:
  - workspace_read_file
  - workspace_list_files
  - fake_edu_list_classes
disable-model-invocation: true
user-invocable: true
always-apply: false
---

# skill.read

Use only read-only tools. List or read the caller's workspace artifacts first. If demo class data is needed, use the allowed Pico school tool and keep the answer scoped to the caller's school.
