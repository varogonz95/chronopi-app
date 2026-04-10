---
name: open-pull-request
description: "Open a GitHub pull request for current changes. Use when: user says 'open a pull request', 'create a PR', 'submit PR', 'push and open PR', or '@openPullRequest'. Creates a branch, stages changes, commits with a conventional commit message, pushes, and opens a PR."
argument-hint: "Optional: branch name or PR title"
---

# Open Pull Request

Create a branch, commit current changes, push, and open a GitHub pull request.

## Prerequisites

- The workspace must be a git repository
- There must be uncommitted changes (staged or unstaged)
- The `gh` CLI must be installed and authenticated

## Procedure

### 1. Identify the repository root

Run `git rev-parse --show-toplevel` to find the repo root. All subsequent git commands must run from this directory.

### 2. Review current changes

Use the `get_changed_files` tool to inspect unstaged and staged diffs. Understand what was changed to generate a meaningful commit message and PR description.

### 3. Create a feature branch off main

Generate a short, descriptive branch name based on the changes (e.g., `fix/add-cffi-dependency`, `feat/dashboard-auth`). Use the pattern `<type>/<short-description>` where type is one of: `feat`, `fix`, `chore`, `docs`, `refactor`, `ci`, `test`.

```
git checkout -b <branch-name> main
```

If the branch already exists, ask the user before overwriting.

### 4. Stage changed files

```
git add -A
```

Only stage files relevant to the change. If there are unrelated changes, ask the user which files to include.

### 5. Commit with a conventional commit message

Write a commit message following the [Conventional Commits](https://www.conventionalcommits.org/) spec:

```
<type>(<optional-scope>): <description>
```

Examples:
- `fix(deps): add cffi and cryptography to requirements`
- `feat(auth): add OAuth callback endpoint`
- `chore(ci): update deploy workflow`

The description should be lowercase, imperative mood, no period at the end. Derive the message from the actual diff content.

```
git commit -m "<conventional-commit-message>"
```

### 6. Push the branch

```
git push -u origin <branch-name>
```

### 7. Open the pull request

Use `gh pr create` to open the PR against the default branch:

```
gh pr create --title "<conventional-commit-message>" --body "<description>" --base main
```

The PR body should include:
- A brief summary of **what** changed and **why**
- A list of key changes (files or features)

Keep it concise — 3-8 lines is ideal.

### 8. Confirm

Report the PR URL back to the user.
