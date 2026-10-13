#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
set -eu
cd "$(dirname "$0")/.."
mkdir -p .work/upstream
clone() {
  name=$1 revision=$2
  path=.work/upstream/$name
  if test -d "$path/.git"; then
    test -z "$(git -C "$path" status --porcelain)" || { echo "Refusing dirty upstream $name" >&2; exit 2; }
  else
    # A fresh --no-checkout clone intentionally has no populated worktree/index.
    git clone --no-checkout "https://github.com/darlinghq/$name.git" "$path"
  fi
  git -C "$path" checkout --detach "$revision"
  git -C "$path" submodule update --init --recursive
}
clone darling 60ba801decee7a00782f74f6be4c8ffb013f79ff
clone darling-metal ae20248dc144beab899e38752f5a530f28a0ea56
clone indium 8423a7d2f053167030d2bc4a227f96243c740667
python3 tools/lock_sources.py
