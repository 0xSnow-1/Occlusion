# Agentic Workflow Guide

## About

### What is Herdr?
Herdr is a terminal workspace manager designed for AI coding agents. It manages persistent sessions, tabs, and panes so you can run multiple agents in parallel without losing context. Think of it as tmux/zellij but built specifically for AI agent workflows.

### What is Treehouse?
Treehouse manages a pool of git worktrees. Each worktree is an isolated copy of your repo. When you run multiple agents, each gets its own worktree so they don't overwrite each other's changes. You grab worktrees when needed and return them when done.

### What is no-mistakes?
No-mistakes is a validation gate that runs your code through a pipeline (rebase, review, test, document, lint, push, PR, CI) before it reaches production. It catches bugs, type errors, and style issues automatically. When it finds problems, it either fixes them itself or asks you to decide.

### How they work together
- **Herdr** → manages your terminal layout (which agent is in which pane)
- **Treehouse** → manages git worktrees (which agent has which copy of the repo)
- **no-mistakes** → validates each agent's work before merging

---

## Daily Startup

### 1. Launch herdr
```bash
herdr
```
This opens your persistent session with tabs/panes configured for parallel agent work.

### 2. Initialize treehouse (one time per repo)
```bash
treehouse init
```

### 3. Spin up agents
In each herdr pane/tab:

```bash
# Pane 1 - You (main feature)
treehouse get
git switch -c feature/chunking
opencode

# Pane 2 - Agent A (evals, tests, etc.)
treehouse get
git switch -c feature/evals
opencode

# Pane 3 - Agent B (prompts, docs, etc.)
treehouse get
git switch -c feature/prompts
opencode
```

Each agent gets an isolated copy of the repo via treehouse. Herdr keeps them organized in your terminal.

**Important:** `treehouse get` creates a worktree but does NOT create a branch. You're in a detached HEAD state. Always run `git switch -c <branch-name>` after getting a worktree.

### 4. Give tasks to each agent
- Pane 1: "Implement the chunker"
- Pane 2: "Write eval tests for document_parser"
- Pane 3: "Refine the system prompt for citations"

---

## When Agents Finish

You're still in the treehouse worktree. The agent's work is already committed on this branch. You can check what it did:

```bash
git log --oneline -3
```

Then validate directly from here (no checkout needed):

```bash
no-mistakes axi run --intent "implemented chunking for RAG pipeline"
```

---

## Validation Pipeline (no-mistakes)

You're already on the correct branch (treehouse put you there). Just run:

```bash
no-mistakes axi run --intent "implemented chunking for RAG pipeline"
```

### Check status
```bash
no-mistakes axi status
```

### Handle gates

When the pipeline stops at a gate, you'll see findings. Choose one:

```bash
# Approve everything, continue
no-mistakes axi respond --action approve

# Let pipeline fix specific findings
no-mistakes axi respond --action fix --findings F1,F2

# Skip this step entirely
no-mistakes axi respond --action skip

# Read full logs for a step
no-mistakes axi logs --step review --full
```

### Ask-user findings

Some findings are marked `ask-user` - only you can decide. The pipeline will pause and show you the options. Pick one:

- `approve` - accept as-is
- `fix` - let pipeline fix it (pass guidance with `--instructions "your guidance"`)
- `skip` - ignore it

### Loop until done
```bash
no-mistakes axi status        # check where you are
no-mistakes axi respond ...   # respond to gate
no-mistakes axi status        # check again
# repeat until outcome
```

### Final outcomes
- `outcome: checks-passed` - PR is ready, CI is green
- `outcome: passed` - PR merged
- `outcome: failed` - fix issues, commit, rerun

---

## After Validation

### Sync pipeline commits
```bash
no-mistakes axi sync
```

### Create PR (if not auto-created)
```bash
git push origin HEAD
gh pr create --base main
```

### Merge
```bash
gh pr merge --merge
```

### Return worktree
```bash
treehouse return
```

### Clean up
```bash
git checkout main
git pull
```

---

## Quick Reference

### Herdr
| Task | Command |
|------|---------|
| Launch herdr | `herdr` |
| Check status | `herdr status` |
| List workspaces | `herdr workspace list` |
| Create workspace | `herdr workspace create <name>` |
| Switch workspace | `herdr workspace focus <name>` |

### Treehouse
| Task | Command |
|------|---------|
| Initialize | `treehouse init` |
| Grab worktree | `treehouse get` |
| Return worktree | `treehouse return` |
| Check pool | `treehouse status` |

### no-mistakes
| Task | Command |
|------|---------|
| Start validation | `no-mistakes axi run --intent "..."` |
| Check status | `no-mistakes axi status` |
| Approve gate | `no-mistakes axi respond --action approve` |
| Fix findings | `no-mistakes axi respond --action fix --findings F1,F2` |
| Skip step | `no-mistakes axi respond --action skip` |
| Sync after run | `no-mistakes axi sync` |
| Rerun pipeline | `no-mistakes rerun` |
| Abort run | `no-mistakes axi abort` |
| Check health | `no-mistakes doctor` |

---

## Config Notes

- Auto-fix enabled for: rebase, lint, test, review, document, ci (3 attempts each)
- Review auto-fix: enabled (findings fixed automatically unless `ask-user`)
- Agent: opencode (uses default model unless overridden in `~/.no-mistakes/config.yaml`)
- Herdr config: `~/.config/herdr/config.toml`
