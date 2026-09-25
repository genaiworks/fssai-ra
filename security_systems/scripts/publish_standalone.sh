#!/usr/bin/env bash
# Publish security_systems/ as its own repository, with its history, so reviewers land on
# a repository that contains only the talk's code and its CI runs at the root.
#
#   1. Create an EMPTY public repository on GitHub (no README, licence or .gitignore),
#      for example github.com/genaiworks/trustkernel.
#   2. From anywhere inside the parent repository, run:
#        bash security_systems/scripts/publish_standalone.sh https://github.com/genaiworks/trustkernel.git
#
# Re-running it later pushes new security_systems/ commits to the same repository.
# It never changes the parent repository's branches or working tree.
set -euo pipefail

url="${1:?usage: publish_standalone.sh <empty-repository-url>}"
root="$(git rev-parse --show-toplevel)"
cd "$root"
[ -d security_systems ] || { echo "run this inside the repository that contains security_systems/" >&2; exit 2; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
git clone --quiet --no-local "$root" "$work/split"
cd "$work/split"
git subtree split --quiet --prefix=security_systems -b standalone
git push "$url" standalone:main
echo "Published security_systems/ history to $url (branch main)."
echo "Next: open the repository's Actions tab and confirm the 'ci' workflow is green."
