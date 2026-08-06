#!/usr/bin/env sh
set -eu

health="$(curl --fail --silent http://localhost:8000/v1/health)"
ready="$(curl --fail --silent http://localhost:8000/v1/ready)"
printf '%s\n%s\n' "$health" "$ready"
