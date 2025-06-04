#!/bin/sh

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
