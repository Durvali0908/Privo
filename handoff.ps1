# Privo - Automatic Claude Handoff
# Creates a snapshot of the current Git/project state.

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

# Create automatic handoff file
$handoff = @"
# Privo - Automatic Handoff

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## Current Git State

Branch:
$branch

Current Commit:
$commit

## Recent Commits

$recentCommits

## Uncommitted Changes

$status

## Instructions for the Next Claude Session

This project is being continued from another Claude session/account.

Before making changes:

1. Inspect the current project files.
2. Read this handoff file.
3. Check the recent Git commits.
4. Understand what has already been implemented.
5. Do not undo existing work.
6. Continue from the current project state.
7. Follow the project's existing architecture and coding rules.
8. Work one file at a time and wait for approval before moving to another file.

IMPORTANT:
The Git repository is the source of truth for the actual code.
This handoff file describes the latest automatically detected project state.
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