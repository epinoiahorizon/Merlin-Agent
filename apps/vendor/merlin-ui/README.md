# vendored merlin-ui

This directory is a **prebuilt copy** of the shared UI package, committed on purpose — including
`dist/`. It is not a source tree that gets rebuilt during install.

## Why `dist/` is in git

Installing Merlin must not require building the UI from source. The installer provisions Python and
Node, then runs the desktop app against these files. Requiring a frontend build at install time would
add a toolchain step to every fresh machine and a new way for installs to fail.

The consequence is deliberate and should be understood by anyone changing this directory:

- **`dist/` is the source of truth for what ships.** Editing it by hand is legitimate here; there is
  no build step that would regenerate it.
- The upstream package it was vendored from lives elsewhere and is not a submodule — this is a
  snapshot, not a live link.
- Changes made upstream do not arrive automatically. Re-vendor the package when you need them.

## If you are auditing the repo

The usual objection — "compiled output should not be in version control" — is correct for a package
that has a build pipeline. This one does not, by design. The trade is deliberate: a simpler install
path in exchange for a vendored blob that must be re-vendored by hand.

See also: `catalog-data/`, which commits generated JSON for the same class of reason (there is no
deployment step that would produce it at fetch time).
