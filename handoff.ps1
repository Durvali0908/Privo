# Privo - Automatic Claude Handoff
# Creates a snapshot of Git state + project context.

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================"
Write-Host "       PRIVO - CLAUDE HANDOFF"
Write-Host "========================================"
Write-Host ""

# Make sure we're inside a Git repository
git rev-parse --is-inside-work-tree *> $null

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: This folder is not a Git repository."
    exit 1
}

# Get current Git information
$branch = git branch --show-current
$commit = git rev-parse --short HEAD
$status = git status --short
$recentCommits = git log -5 --oneline

# Read existing project status
$projectStatus = ""

if (Test-Path "PROJECT_STATUS.md") {
    $projectStatus = Get-Content "PROJECT_STATUS.md" -Raw
}
else {
    $projectStatus = "PROJECT_STATUS.md was not found."
}

# Create automatic handoff file
$handoff = @"
# Privo - Automatic Claude Handoff

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

---

## Current Git State

Branch:
$branch

Current Commit:
$commit

## Recent Commits

$recentCommits

## Uncommitted Changes

$status

---

## Project Context

The following is the current project documentation:

$projectStatus

---

## Instructions for the Next Claude Session

This project is being continued from another Claude session/account.

Before making changes:

1. Read this entire handoff file.
2. Inspect the current project files.
3. Check the recent Git commits.
4. Understand what has already been implemented.
5. Do not undo existing work.
6. Continue from the current project state.
7. Follow the project's existing architecture and coding rules.
8. Work one file at a time.
9. Explain the reasoning before generating code.
10. Wait for explicit approval before moving to another file.

IMPORTANT:

The Git repository is the source of truth for the actual code.

PROJECT_STATUS.md contains the stable project context.

This handoff file combines the Git state and project context
so another Claude account can understand the project quickly.

"@

$handoff | Set-Content -Path "CLAUDE_HANDOFF.md" -Encoding UTF8

Write-Host ""
Write-Host "Handoff created successfully:"
Write-Host "CLAUDE_HANDOFF.md"
Write-Host ""
Write-Host "Current branch: $branch"
Write-Host "Current commit: $commit"
Write-Host ""

if ($status) {
    Write-Host "WARNING: You have uncommitted changes."
    Write-Host "Review them before switching Claude accounts."
}
else {
    Write-Host "Working tree is clean."
}

Write-Host ""
Write-Host "Handoff preparation complete."