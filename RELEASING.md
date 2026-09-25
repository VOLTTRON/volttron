# Releasing VOLTTRON

This document describes how a VOLTTRON release is prepared, tagged, and
published. It reflects the process this repository has actually used, drawn
from its release branches and tags, not a generic template. Where past
practice was unclear or inconsistent, that is stated plainly, alongside what
this document proposes going forward. Nothing in this document is automated
unless section 11 says otherwise.

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

The latest tag at the time this document was written is 9.0.4.

## 2. Where release work happens

A release is prepared on a branch named `releases/<version>` (for example
`releases/9.0.4`), cut from `develop`.

Past practice here is worth stating plainly rather than idealizing. For the
9.0.4 release, the commits that bumped the version string and updated release
facing documentation were made in the same commit sequence that also became
part of `develop`'s own history: they carry the same commit hashes on both
branches. The `releases/9.0.4` branch did not stay a long lived line of its
own divergent commits; it ended up pointing at a commit that `develop` also
reached. In practice, the release branch functioned as a stable name for a
chosen point in the ongoing `develop` history, once the release preparation
commits landed there.

Going forward, treat `releases/<version>` as cut from `origin/develop` at the
commit chosen as the release point. Make the version bump and any
release-facing documentation changes (section 3) as commits on that branch.
If those same commits are also cherry-picked or merged back onto `develop`,
the two histories stay consistent by construction, matching what was
observed for 9.0.4.

If `main` has commits that are not yet on `develop` (see section 7), merge
`main` into the release branch before finalizing it, the way `releases/9.0.4`
merged `main` in before its release. This keeps the release from silently
dropping a fix that only exists on `main`.

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

## 4. Tagging and publishing the release

The tag `X.Y.Z` is created on the release branch, at the commit that carries
the version bump, before that branch is merged into `main`. This repository
does not prefix release tags with `v`: of 38 tags, only 2 carry a `v`, both
2014-era pre-releases, and every 8.x and 9.x tag, 9.0.4 included, is bare.
Use the bare form, matching section 1's own naming of the latest tag.

This is what the 9.0.4 tag shows in another way too: it points at the head
of `releases/9.0.4`, not at the commit that later merged that branch into
`main`. Continue that practice: tag the release branch tip, not the merge
commit on `main`.

A lightweight tag is what every 8.x and 9.x tag in this repository actually
is, confirmed by reading each tag object: it resolves directly to a commit
rather than to a separate annotated tag object. A lightweight tag is
therefore consistent with practice and is what this document asks for.

That tag is a weaker record than calling it "definitive" without
qualification would suggest, and it deserves the same caveat section 6 gives
branch protection rather than none. Nothing in this repository protects a
tag: the tag-protection endpoint returns 404 and the repository's rulesets
list is empty. A lightweight tag also carries no tagger, date, message or
signature, and anyone with push access can move or delete it. Once the
rebase merge in section 6 lands a release, the commit `main` shows for that
version is a new commit object, not the tagged one, and because this
repository deletes a branch on merge, the tagged commit is then reachable
from nothing but the tag itself. So: the tag is the record of what a version
contained only for as long as the tag survives, and nothing here currently
guards that survival. Switching to an annotated tag, or asking a maintainer
with repository-settings authority to add tag protection for version tags,
would each narrow this gap; both are proposals, not current practice, and
neither is assumed by the rest of this document.

Once the tag exists, a maintainer with release authority (section 10)
creates a GitHub Release for it: not a draft, named after the version, with
release notes summarizing what changed since the previous release. Every
prior 8.x and 9.x release in this repository has a published, non-draft
Release object of this kind, most combining a short hand-written summary
with an auto-generated pull-request list. This step is manual today, like
everything else in this document (section 11); nothing in this repository's
CI creates it.

## 5. What gets released is not enforced by this document

This document describes the branch and tag mechanics. It does not, by
itself, guarantee that the code on the release branch is ready: that is a
judgment for whoever approves the release (section 10), informed by the
project's test suite and review process.

## 6. Merging the release into main

The release branch is merged into `main` through a pull request, using a
rebase merge. Do not squash it: this repository has squash merging turned
off at the repository level, and the release history is worth keeping
intact. Do not land it as an ordinary merge commit either: `main`'s branch
protection requires a linear history, and an ordinary merge commit cannot
satisfy that. Rebase merge is the strategy that satisfies both the
linear-history requirement and the no-squash rule, and it is the one this
project uses to land a release into `main`.

This differs from how the 9.0.4 release actually landed: that pull request
merged into `main` as an ordinary two-parent merge commit. A reader
comparing the two should read the difference as history predating this
policy, not as an error in either direction; the rebase merge requirement is
what this project has settled on for every release going forward.

Branch protection is configuration, not code, and it can change
independently of this document. Confirm the linear-history and no-squash
settings on `main` are still what this section assumes before relying on
them.

## 7. Reconciling develop and main

This is the part a generic release process description will not have, and
the part most likely to cause a problem if skipped.

`develop` is the active branch: nearly everything lands there first. `main`
only moves when a release is merged into it. Between releases, `main` and
`develop` diverge, and it is easy for that gap to go unnoticed because
nothing forces it closed.

At the time this document was written, `main` carried two commits that
`develop` did not: the merge that landed the 9.0.4 release, and a later,
unrelated documentation wording fix made directly on `main`. Meanwhile
`develop` carried many more commits that `main` did not, none of which had
been folded back into `main` since. This repository's history does show
occasional "merge main into develop" commits, so reconciling in that
direction is established practice, but the most recent one found predates the
9.0.4 release by roughly a year, and none has happened since. In other words,
the practice exists but has not been kept up, and the gap has been allowed to
grow.

Propose, as a standing part of every release, doing both halves of this
explicitly rather than leaving either to chance:

- Before finalizing a release branch, merge `main`'s current tip into it
  (section 2), so nothing that only exists on `main` is lost when the release
  branch replaces `main`'s history at the next merge.
- After the release branch is merged into `main`, merge `main` back into
  `develop` (or cherry-pick the release-specific commits: the version bump
  and any documentation changes made directly on the release branch) so
  `develop` carries the same version marker `main` now has, and so any fix
  made directly on `main` is not permanently absent from `develop`.

The cost of the second step grows with how long it has been skipped: doing it
right after every release is a small, usually conflict-free merge; doing it
after a long gap, as would be the case today, means resolving conflicts
across a much larger and more diverged set of files. Doing it every release
is what keeps the cost small.

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
Release for that version (section 4) is itself published and not a draft,
not before. A fix that only exists on a branch a user cannot yet install, or
a release a reader cannot yet find, is not a fix a published advisory can
responsibly point to.

Coordinate the timing so the advisory goes out once a reader can confirm,
from the repository's Releases page or its API, that the version containing
the fix is published rather than a draft, and confirm the advisory names
that version.

## 10. Who decides what

Preparing a release, proposing the version number, and drafting the branch
and tag is not the same decision as authorizing that release to ship.
Whoever prepares a release proposes the version number and the branch
contents; a project maintainer with release authority reviews and approves
before anything is tagged or published.

"Merging a pull request" and "releasing a version" are two separate
decisions, and approval of one does not by itself authorize the other. A
change can be merged to `develop`, or even merged into a release branch,
well before anyone decides that branch should become a published release.

## 11. What is not automated today

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

Three steps in this document are hard or impossible to undo, and none of the
sections above say what to do if each one fails.

- The tag (section 4) is created before the release branch is merged into
  `main`. If the release branch is then reworked or rejected, the tag
  already names a commit that never lands anywhere durable. Delete that tag
  and create a new one once a release point is actually ready. Do not reuse
  the old tag name for a different commit: a moved tag with the same name as
  something once published is exactly the weak point section 4 describes.
- The rebase merge into `main` (section 6) can conflict. Resolve the
  conflict on the release branch itself, then rebase again, so the branch's
  own tested history is what actually lands, rather than resolving it inside
  the pull request's own rebase tooling. If the conflicts are large enough
  that this is impractical, re-cut the release branch from a current
  `origin/develop` and start over, rather than forcing a resolution nobody
  has reviewed.
- Publishing a security advisory (section 9) is irreversible in the
  disclosure sense: once details are public, they cannot be made
  confidential again. If a defect in the advisory itself is found afterward,
  such as a wrong version or a wrong description, correct it in place and
  note the correction and its date within the advisory. Do not delete it and
  post a new one in its place.
