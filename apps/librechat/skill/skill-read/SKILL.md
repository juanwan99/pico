---
name: skill-read
displayTitle: skill.read
description: Use this skill when the answer needs read-only school data.
allowed-tools:
  - fake_edu_list_classes
disable-model-invocation: true
user-invocable: true
always-apply: false
---

# skill.read

Use only read-only school tools. If class data is needed, read it through the allowed Pico tool and keep the answer scoped to the caller's school.

