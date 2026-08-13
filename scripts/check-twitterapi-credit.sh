#!/usr/bin/env bash
# Check the twitterapi.io account balance / remaining credit.
#
# Usage:
#   export TWITTERAPI_IO_API_KEY=your_key
#   ./scripts/check-twitterapi-credit.sh
#
# The balance endpoint is not listed in docs.twitterapi.io/llms.txt, so this
# probes the known candidate paths and prints whichever one answers.

set -uo pipefail

if [[ -z "${TWITTERAPI_IO_API_KEY:-}" ]]; then
  echo "TWITTERAPI_IO_API_KEY is not set." >&2
  exit 1
fi

BASE="https://api.twitterapi.io"

for path in \
  "/oapi/my/info" \
  "/twitter/user/me" \
  "/oapi/my/account" \
  "/my/info"
do
  echo "== GET ${BASE}${path}"
  code=$(curl -sS -o /tmp/twapi_body -w '%{http_code}' \
    -H "x-api-key: ${TWITTERAPI_IO_API_KEY}" \
    "${BASE}${path}")
  echo "   HTTP ${code}"
  if [[ "$code" == "200" ]]; then
    echo "   --- response ---"
    cat /tmp/twapi_body
    echo
    echo "   ^ balance found at ${path}"
    exit 0
  fi
done

echo "No balance endpoint responded 200. Read the credit from the dashboard instead." >&2
exit 1
