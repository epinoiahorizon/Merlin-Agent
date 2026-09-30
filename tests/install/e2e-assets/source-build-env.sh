#!/usr/bin/env bash
# OLD and NEW must stamp the checked-out source, not the CI driver's ref.
# A subshell preserves the workflow's identity and the git URL redirect.
source_build_env() (
  unset GITHUB_SHA GITHUB_REF GITHUB_REF_NAME GITHUB_HEAD_REF GITHUB_BASE_REF
  unset MERLIN_BUILD_COMMIT MERLIN_PAYLOAD_TAG MERLIN_PAYLOAD_VERSION MERLIN_DESKTOP_VARIANT
  "$@"
)