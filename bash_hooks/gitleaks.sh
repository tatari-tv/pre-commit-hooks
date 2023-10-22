#!/usr/bin/env bash

set -euo pipefail

version=8.18.0
# shellcheck disable=SC2034 # variables used in sha_accessor via indirect expansion
darwin_x64_sha=2b5dc091a200b15b7f77d190de137da034b041f8901a0264015d29aa5c272714
# shellcheck disable=SC2034
darwin_arm64_sha=bad6f03ab5efcaf262adca29fc2de0988f9f4ff08bec448db4fc5a3da769b82f
# shellcheck disable=SC2034
linux_x64_sha=6e19050a3ee0688265ed3be4c46a0362487d20456ecd547e8c7328eaed3980cb
# shellcheck disable=SC2034
linux_arm64_sha=c19c2af7087e1c2bd502f85ae92e6477133fc43ce17f5ea09f63ebda6e3da0be

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m | tr '[:upper:]' '[:lower:]')"
if [ "${arch}" = "x86_64" ]; then
  arch="x64"
fi

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "${tmp_dir}"
}

trap cleanup EXIT

sha_accessor="${os}_${arch}_sha"
sha="${!sha_accessor}"

if [ -z "${sha}" ]; then
  echo "ERROR: unsupported platform ${os} ${arch}"
  exit 1
fi

shabin="shasum"
if ! command -v "${shabin}" >/dev/null; then
  shabin="sha256sum"
  if ! command -v "${shabin}" >/dev/null; then
    echo "ERROR: failed to find sha256sum or shasum"
    exit 1
  fi
fi

filename="gitleaks_${version}_${os}_${arch}.tar.gz"
url="https://github.com/gitleaks/gitleaks/releases/download/v${version}/${filename}"

binary_dir="${HOME}/.cache/pre-commit/gitleaks/${os}-${arch}-${version}"
binary=${binary_dir}/gitleaks

if [[ ! -x "${binary}" ]]; then
  # downloading gitleaks binary
  mkdir -p "${binary_dir}"

  if ! curl --fail --location --retry 5 --retry-connrefused --silent --output "${tmp_dir}/gitleaks.tar.gz" "${url}"; then
    echo "ERROR: failed to download gitleaks"
    exit 1
  fi

  if echo "${sha}  ${tmp_dir}/gitleaks.tar.gz" | ${shabin} --check --status; then
    tar -xzf "${tmp_dir}/gitleaks.tar.gz" -C "${tmp_dir}"
    chmod +x "${tmp_dir}/gitleaks"

    # Protect against races of concurrent hooks downloading the same binary
    if [[ ! -x "${binary}" ]]; then
      mv "${tmp_dir}/gitleaks" "${binary}"
    fi
  else
    echo "ERROR: sha mismatch"
    exit 1
  fi

fi

exec "${binary}" protect --verbose --redact --staged
