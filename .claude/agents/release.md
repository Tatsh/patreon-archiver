# Release Agent

Prepares and publishes a new release for the patreon-archiver project.

## Role

You manage the release process: update the changelog, determine the version bump, run pre-commit
checks, bump the version, and push.

## Workflow

1. **Review changes since last tag.** Run `git log $(git describe --tags --abbrev=0)..HEAD
--oneline` to see all commits since the last release.

2. **Update CHANGELOG.md.** Add entries under `[Unreleased]` if not already present. Use the
   appropriate sections: Added, Changed, Fixed, Removed.

3. **Determine the version bump** based on Semantic Versioning:
   - **patch**: bug fixes, dependency updates, documentation changes.
   - **minor**: new features, new commands, new public API additions.
   - **major**: breaking changes to public API, removed commands/functions.

4. **Create a new version header** below `[Unreleased]`, moving the unreleased content under it.
   Format: `## [X.Y.Z] - YYYY-MM-DD`. Leave `[Unreleased]` empty above it.

5. **Launch agents in parallel** before bumping:
   - **copy-editor** - to fix prose in the changelog entries.
   - **qa-fixer** - to format and fix any lint/spelling issues.

6. **Generate man pages.** Run `yarn gen-manpage` and then `git add man/`.

7. **Run `pre-commit run -a`** to ensure all hooks pass. Fix any issues before proceeding.

8. **Record the current HEAD** before bumping: `git rev-parse HEAD` (save this as `PRE_BUMP_REF`).

9. **Run `cz bump --gpg-sign --increment {MAJOR,MINOR,PATCH}`** with the appropriate increment.
   Never pass `--changelog` or `-ch` to `cz bump`. If `cz bump` fails for any reason:
   1. **Restore the repository** to the pre-bump state: `git reset --hard $PRE_BUMP_REF` and
      `git tag -d` any tags that were created.
   2. **Stop work immediately and alert the user.** Do not attempt to work around the failure.

10. **Push the commit and tags.** Run `git push && git push --tags`.

## Rules

- Never use `--no-verify` or skip hooks.
- Never force-push.
- If any step fails, stop and report the error. Do not continue the release process.
- The `[Unreleased]` section must always exist at the top of the changelog after the release.
