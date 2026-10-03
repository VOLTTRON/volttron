# Releasing VOLTTRON

This document describes how a VOLTTRON release is prepared, tagged, and
published. It is drawn from this repository's release branches and tags, not
from a generic template. Nothing in this document is automated unless
section 11 says otherwise.

## 1. Version policy

VOLTTRON follows semantic versioning, MAJOR.MINOR.PATCH, with one project
specific constraint: the major version stays at 9 and does not go above it.
Only MINOR and PATCH move.

- PATCH: bug fixes and security fixes that add no new capability a caller can
  see. No behavior a working caller depended on changes.
- MINOR: new, backward compatible capability. This includes a new
  enforcement mechanism, a new configuration option, or a new administrative
  capability, even when it ships alongside fixes.
- A change that breaks an existing caller would ordinarily be MAJOR. Because
  the major version is fixed at 9, such a change is not released as a normal
  MINOR or PATCH; it needs its own decision by a project maintainer with
  release authority before it ships at all.

Read the latest release tag from `git tag` or the repository's Releases page;
the next version is chosen against it.

## 2. Where release work happens

A release is prepared on a branch named `releases/<version>` (for example
`releases/9.0.4`). Cut it from `origin/develop` at the commit chosen as the
release point. Make the version bump and any release-facing documentation
changes (section 3) as commits on that branch. The 9.0.4 release worked the
same way: its preparation commits carry the same hashes on `develop`, so the
two histories stay consistent.

Before finalizing the release branch, merge `main` into it every release, even
when `main` appears to be level with `develop` (section 7). This keeps the
release from silently dropping a fix that only exists on `main`. Resolve any
conflict from that merge on the release branch, and do it before the tag is
created (section 4), so the tagged tip is the content that lands on `main`.

## 3. What gets updated in a release

Two files carry the authoritative version string, confirmed by reading them
and by how the 9.0.4 release changed them:

- `volttron/platform/__init__.py`, the `__version__` assignment. `setup.py`
  reads this file directly to set the package version; there is no separate
  version declared in `setup.py` itself.
- `docs/source/conf.py`, the Sphinx `version` and `release` assignments.

Both are plain string literals, are not generated from the git tag or from
each other, and nothing enforces that they agree: no script and no CI step
reads either one back to check it against the other or against the tag. A
release bumps both by hand, or by a script that writes both, and then
confirms them before tagging:

    grep "__version__" volttron/platform/__init__.py
    grep -E "^(version|release) = " docs/source/conf.py

Both commands must print the same version being released, and that version
must match the tag about to be created (section 4).

A small number of other files mention the version number in prose rather
than as a machine-read field: `README.md` and
`docs/source/introduction/platform-install.rst` both state the VOLTTRON
version and the Python version it was tested against. The 9.0.4 release
updated these too, in a separate commit from the version bump. They are not
required for the package or the docs build to report the right version, but
leaving them stale misleads a reader, so update them along with the version
bump when their content is affected by the release.

## 4. Tagging the release

The tag `X.Y.Z` is created on the release branch, at the commit that carries
the version bump and the merge of `main` (section 2), before that branch is
merged into `main`. This repository
does not prefix release tags with `v`: of 38 tags, only 2 carry a `v`, both
2014-era pre-releases, and every 8.x and 9.x tag, 9.0.4 included, is bare.
Use the bare form, matching section 1's own naming of the latest tag.

Tag the release branch tip, not the merge commit on `main`; the 9.0.4 tag
likewise points at the head of `releases/9.0.4`. Create the tag only after a
maintainer with release authority has approved the release (section 10).

Release tags are annotated, so each carries a tagger, a date and a message:

    git tag -a X.Y.Z -m "VOLTTRON X.Y.Z" <release-branch-tip-sha>
    git push origin X.Y.Z

Verify it with `git cat-file -t X.Y.Z`, which prints `tag` for an annotated
tag and `commit` for a lightweight one. That checks only the local tag, so
also confirm the push reached the remote: `git ls-remote --tags origin X.Y.Z`
prints a line, and an empty result means it did not land. The existing 8.x and
9.x tags are lightweight and are left as they are.

Once a tag is pushed it is never moved, deleted and re-created, or reused for a
different commit. Any change after tagging means a new version: bump it
(section 3), create a new tag, and treat the old one as abandoned (section 12).

The tag is the record of what a version contained only for as long as the tag
survives. This repository deletes a branch on merge, but the merge commit in
section 6 brings the tagged commit into `main`, so `main` still contains it
after the branch is gone. An annotated tag can still be moved
or deleted by anyone with push access, and the repository has no tag
protection: its rulesets list is empty and no tag rule exists. A maintainer
with repository-settings authority adds a ruleset protecting version tags as a
one-time setup step; until that is done, treat the tag as unprotected.

## 5. What gets released is not enforced by this document

This document describes the branch and tag mechanics. It does not, by
itself, guarantee that the code on the release branch is ready: that is a
judgment for whoever approves the release (section 10), informed by the
project's test suite and review process. The test workflows run on pushes to
`develop` and `releases/**` and on pull requests into `main`, so check that
they passed on the release branch tip and on the release pull request before
approving. Pushes to `main` do not trigger them.

## 6. Merging the release into main, then publishing it

The release branch is merged into `main` through a pull request, using a
merge commit (`gh pr merge <n> --merge`). Never squash it: this repository has
squash merging turned off at the repository level, and the release history is
worth keeping intact. A merge commit keeps the tagged release commit reachable
from `main`. The repository also allows a rebase merge, and `main`'s protection
does not require linear history, so the choice rests on the person merging;
this project's policy is the merge commit. The 9.0.4 pull request merged the
same way, as an ordinary two-parent merge commit.

`main`'s protection requires one approving review and has the code-owner
setting on. That setting has no effect without a CODEOWNERS file, and this
repository has none (the contents API returns 404 for `CODEOWNERS`,
`.github/CODEOWNERS` and `docs/CODEOWNERS`), so one approval from anyone with
write access suffices. Adding a CODEOWNERS file is a maintainer decision and
is not part of a release. The author of the pull request cannot supply that
approval, and admin enforcement is off, so an administrator can merge without
it. Follow the approval requirement anyway.

Branch protection is configuration, not code, and it can change independently
of this document. A maintainer with admin rights reads the current settings
with `gh api repos/VOLTTRON/volttron/branches/main/protection`; anyone else
reads the merge options on the pull request itself.

Publish nothing until the merge has landed. Once the release pull request has
merged into `main` (confirm with `gh pr view <n> --json state`, which must read
`MERGED`), a maintainer with release authority (section 10) creates a GitHub
Release for the tag: not a draft, named after the version, with release notes
summarizing what changed since the previous release. Every 8.x and 9.x tag in
this repository except `8.0` has a published, non-draft Release object of this
kind (checked with `gh api repos/VOLTTRON/volttron/releases`), most combining a
short hand-written summary with an auto-generated pull-request list. This step
is manual, like everything else in this document (section 11); nothing in this
repository's CI creates it. Publish the Release before any advisory that
depends on it (section 9).

## 7. Reconciling develop and main

This is the part a generic release process description will not have, and
the part most likely to cause a problem if skipped.

`develop` is the active branch: nearly everything lands there first. `main`
only moves when a release is merged into it. Between releases, `main` and
`develop` diverge, and it is easy for that gap to go unnoticed because
nothing forces it closed.

Left alone, the gap grows unnoticed, as it did before the 9.0.4 release
and again after it. Every release does both halves of the reconciliation
explicitly rather than leaving either to chance. Run `git fetch --tags origin`
first, because the next command reads remote-tracking refs that are only as
current as the last fetch. Then check the current state with
`git rev-list --left-right --count origin/develop...origin/main`, which
prints the commits only on `develop` and the commits only on `main`.

- Before finalizing a release branch, merge `main`'s current tip into it
  (section 2), so nothing that only exists on `main` is lost when the release
  branch is merged into `main`.
- After the release branch is merged into `main`, merge `main` back into
  `develop` through a pull request, as a merge commit and never a squash, so
  `develop` carries the same version marker `main` now has, and so any fix
  made directly on `main` is not permanently absent from `develop`. If the
  merge conflicts, review each conflicted hunk rather than taking one side
  wholesale. Keep a fix that exists only on `main`, and keep the released
  version strings in section 3; after resolving, confirm both files read the
  released version. Taking the `develop` side blindly drops a `main`-only fix
  and can undo the version.

The cost of the second step grows with how long it has been skipped: doing it
right after every release is a small, usually conflict-free merge; doing it
after a long gap means resolving conflicts across a much larger and more
diverged set of files.

## 8. Closing issues

A pull request's `Fixes #NNN` (or similar) keyword only closes the
referenced issue automatically when the pull request merges into the
repository's default branch. This repository's default branch is `main`, and
day to day development work merges into `develop`, not `main`. That means an
issue is not closed automatically when the fix merges to `develop`; close it
by hand, with a comment naming the commit or merge that carries the fix, so a
later reader can find the change without guessing which release it shipped
in.

## 9. Publishing security advisories

When a release includes a fix for an issue that was handled under
coordinated disclosure, publish the corresponding advisory once the GitHub
Release for that version (section 6) is itself published and not a draft,
not before. A fix that only exists on a branch a user cannot yet install, or
a release a reader cannot yet find, is not a fix a published advisory can
responsibly point to.

Coordinate the timing so the advisory goes out once a reader can confirm,
from the repository's Releases page or its API, that the version containing
the fix is published rather than a draft, and confirm the advisory names
that version.

## 10. Who decides what

Preparing a release, choosing the version number, and drafting the branch
and tag is not the same decision as authorizing that release to ship.
Whoever prepares a release puts forward the version number and the branch
contents; a project maintainer with release authority reviews and approves
before anything is tagged or published.

"Merging a pull request" and "releasing a version" are two separate
decisions, and approval of one does not by itself authorize the other. A
change can be merged to `develop`, or even merged into a release branch,
well before anyone decides that branch should become a published release.

## 11. What is manual

There is no release workflow in this repository's CI configuration. All ten
GitHub Actions workflow files under `.github/workflows` run tests or static
analysis (`code_analysis.yml` and nine `pytest-*` workflows); none build a
release artifact, push a package, or create a tag. The `.gitlab-ci.yml`
pipeline likewise only runs tests. Concretely, none of the following happen
automatically: bumping the version strings, creating the release branch,
tagging, building or publishing a distributable package, building or pushing
a container image, drafting release notes, or creating a published release
from a tag. Every step in this document is done by hand until that changes.

## 12. When a step fails

Three steps in this document are hard or impossible to undo, so each has a
recovery rule here.

- The tag (section 4) is created before the release branch is merged into
  `main`, and nothing is published until after the merge (section 6). If the
  release branch is then reworked or rejected, the tag names a commit that
  never lands anywhere durable, but no Release or advisory points at it. Do not
  move, delete and re-create, or reuse that tag: any fix after tagging is a new
  version with a new bump (section 3) and a new tag. Leave the abandoned tag in
  place, or delete it only if nothing refers to it, and never after a Release
  or advisory has been published for it.
- The merge into `main` (section 6) can conflict. Resolve the conflict on the
  release branch itself by merging `main` into it before the tag is created
  (section 2), then merge the pull request, so the resolution is reviewed on
  the branch rather than made inside the pull request's own tooling. If a
  conflict only appears after the tag exists, the tagged tip is no longer what
  would land: abandon that tag and release under a new version. If the
  conflicts are large enough that this is impractical, re-cut the release
  branch from a current `origin/develop` and start over, rather than forcing a
  resolution nobody has reviewed.
- Publishing a security advisory (section 9) is irreversible in the
  disclosure sense: once details are public, they cannot be made
  confidential again. If a defect in the advisory itself is found afterward,
  such as a wrong version or a wrong description, correct it in place and
  note the correction and its date within the advisory. Do not delete it and
  post a new one in its place.
