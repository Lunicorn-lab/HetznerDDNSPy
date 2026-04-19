---
description: Draft a CHANGELOG.md entry from git log since the last tag.
---

1. Find the latest git tag with `git describe --tags --abbrev=0`.
2. Read commits since that tag:
   `git log --pretty=format:'- %s (%h)' <tag>..HEAD`.
3. Group them into sections (`Added`, `Changed`, `Fixed`, `Security`,
   `Removed`) following Keep a Changelog.
4. Use **Conventional Commit** types to classify: `feat:` → Added,
   `fix:` → Fixed, `security:` → Security, `refactor:`/`chore:` → Changed.
5. Write the draft into a new `## [Unreleased]` section at the top of
   `CHANGELOG.md`. Do not commit.
6. Flag any commit mentioning "BREAKING CHANGE" — these belong under
   `Changed` with a **BREAKING** prefix and need a migration note.

End with the proposed version bump (`major|minor|patch`) and a one-sentence
justification.
