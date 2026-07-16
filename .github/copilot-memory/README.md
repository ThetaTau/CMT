# Copilot project memory

This folder is an exported snapshot of the GitHub Copilot **agent memory** for this
repository — the accumulated "lessons learned," conventions, gotchas, and test
patterns discovered across past Copilot coding sessions. It is committed to git so
the knowledge travels with the repo and every teammate's Copilot can use it.

## Contents

- **[`thetatauCMT-status.md`](thetatauCMT-status.md)** — the main repository memory:
  dated engineering notes, feature-by-feature history, subtle bugs and their fixes,
  test-suite state, and repo-specific pitfalls. Start here.
- **[`sessions/`](sessions/)** — per-conversation planning/history docs from
  individual past sessions (kept as historical reference; may overlap with the
  status doc above).

## How teammates use it

The repository's [`.github/copilot-instructions.md`](../copilot-instructions.md)
points Copilot at this folder, so the agent will discover and read these notes when
working in the repo — no manual step required. Consult `thetatauCMT-status.md`
before making changes; it documents conventions and traps that are not obvious from
the code alone.

## Re-importing into Copilot's live memory (optional)

The files here are a *copy*. Copilot's live memory store lives outside the repo, in
VS Code's per-workspace storage:

```
<VS Code user data>/User/workspaceStorage/<workspace-hash>/GitHub.copilot-chat/memory-tool/memories/
```

To seed a fresh environment's live memory from this snapshot, ask Copilot in that
workspace to "import the repo memory from `.github/copilot-memory/`," or manually
copy `thetatauCMT-status.md` into that store's `repo/` subfolder. This is only needed
if you want the agent's *persistent* memory (not just on-demand reads) pre-populated.

## Keeping it current

This is a point-in-time export. Re-run the export (copy the live
`memory-tool/memories/repo/*.md` back into this folder) whenever the memory has
grown meaningfully, and commit the update.
