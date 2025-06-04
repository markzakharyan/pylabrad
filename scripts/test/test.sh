#!/bin/sh

set -e

# Ensure Java 17+ is available
JAVA_STR=$(java -version 2>&1 | awk -F\" '/version/ {print $2}')
JAVA_MAJOR=$(echo $JAVA_STR | cut -d. -f1)
if [ "$JAVA_MAJOR" = "1" ]; then
  JAVA_MAJOR=$(echo $JAVA_STR | cut -d. -f2)
fi
if [ "$JAVA_MAJOR" -lt 17 ]; then
  echo "Java 17 or newer required; found $JAVA_STR" >&2
  exit 1
fi

export LABRADHOST=localhost
export LABRADPASSWORD=testpass
export LABRADPORT=7777
export CI=true

# Ensure scalabrad is installed and available
SCALABRAD_VERSION="${SCALABRAD_VERSION}"
if ! command -v labrad >/dev/null; then
  if [ -z "$SCALABRAD_VERSION" ]; then
    echo "SCALABRAD_VERSION not set; defaulting to 0.9.0"
    SCALABRAD_VERSION=0.9.0
  fi
  echo "Installing scalabrad version $SCALABRAD_VERSION"
  bash "$(dirname "$0")/install-scalabrad.sh"
  export PATH="$PATH:$HOME/scalabrad-$SCALABRAD_VERSION/bin"
else
  echo "Using existing scalabrad at $(command -v labrad)"
fi
export SCALABRAD_VERSION

echo "labrad executable: $(command -v labrad)" >&2
LABRAD_VERSION=$(grep -m1 PROG_VERSION "$(command -v labrad)" | cut -d= -f2)
echo "labrad version: ${LABRAD_VERSION}" >&2

# Install python dependencies if needed
if ! python -c "import twisted" 2>/dev/null; then
  python3 -m pip install --break-system-packages --ignore-installed -r requirements.txt
  python3 -m pip install --break-system-packages pytest
fi
python3 -m pip install --break-system-packages --no-deps .

# start labrad manager
labrad 1>.labrad.log 2>.labrad.err.log &
LABRAD_PID=$!
trap 'kill $LABRAD_PID 2>/dev/null' EXIT
sleep 20

# run the tests
pytest -v .
STATUS=$?

echo "=== .labrad.log ===" && cat .labrad.log && echo

exit $STATUS
