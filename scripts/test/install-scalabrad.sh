#!/bin/sh

# exit on any error
set -e

# Use default version if not provided
SCALABRAD_VERSION="${SCALABRAD_VERSION:-0.9.0}"

ARCHIVE="scalabrad-${SCALABRAD_VERSION}.tar.gz"

URL_BASE="https://github.com/markzakharyan/scalalbrad/releases/download/v${SCALABRAD_VERSION}"

echo "Fetching scalabrad ${SCALABRAD_VERSION} from ${URL_BASE}" >&2

# check to see if scalabrad folder is empty
if [ ! -d "$HOME/scalabrad-${SCALABRAD_VERSION}/bin" ]; then
  wget "${URL_BASE}/${ARCHIVE}" -O "${HOME}/${ARCHIVE}"
  cd "$HOME" && tar -xvf "$ARCHIVE"
else
  echo "Using cached scalabrad-${SCALABRAD_VERSION}." >&2
fi
