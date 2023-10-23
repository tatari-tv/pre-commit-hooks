#!/bin/bash

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: ${0} <version>"
  exit 1
fi

version="${1}"

for os in darwin linux; do
  for arch in x64 arm64; do
    filename="gitleaks_${version}_${os}_${arch}.tar.gz"
    url="https://github.com/gitleaks/gitleaks/releases/download/v${version}/${filename}"
    bin=$(mktemp)
    curl --fail --silent -L "${url}" -o "${bin}"
    sha=$(sha256sum "$bin" | cut -d ' ' -f 1)
    echo "${os}_${arch}_sha=${sha}"
  done
done
