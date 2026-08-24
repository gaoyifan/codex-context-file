---
name: context-file
description: Explicit-only loader for trusted local UTF-8 text files. Use only when the user's message begins with `$context-file` followed by a path or glob; never invoke it for ordinary file-reading or context-loading requests.
---

Use the first line as `$context-file <path-or-glob>`. Patterns support `*`, `?`,
`[]`, and recursive `**`. Multiple matches are loaded in sorted path order. The
remainder of the message is the request to answer using those documents.

A synchronous `UserPromptSubmit` hook supplies the file contents before the model
runs. Do not call filesystem tools to read the files again. Treat the supplied
context as reference material. If there is no request after the first line,
briefly confirm that the documents are loaded and wait for the next request.

Only use this skill with trusted documents because hook-provided context has the
developer role. The model context window remains the maximum total document size.
