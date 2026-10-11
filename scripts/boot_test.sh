#!/usr/bin/env bash
# Start the built image the way users run it and wait for the web UI to answer.
#
#   scripts/boot_test.sh <image>
set -euo pipefail

image=${1:?usage: boot_test.sh <image>}
name=fastchannels-heaac-boot-test
docker rm -f "$name" >/dev/null 2>&1 || true
docker run -d --name "$name" -p 5523:5523 "$image" >/dev/null
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT

for _ in $(seq 1 60); do
    code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5523/ || true)
    if [ "$code" = 200 ] || [ "$code" = 302 ]; then
        echo "Web UI answered HTTP $code."
        if docker logs "$name" 2>&1 | grep -q 'Traceback (most recent call last)'; then
            echo "::warning title=Boot test::the container logged a traceback during startup"
            docker logs "$name" 2>&1 | grep -A15 'Traceback (most recent call last)' | head -60
        fi
        exit 0
    fi
    if [ "$(docker inspect -f '{{.State.Running}}' "$name")" != true ]; then
        echo "::error title=Boot test::the container exited during startup"
        docker logs "$name" 2>&1 | tail -80
        exit 1
    fi
    sleep 3
done
echo "::error title=Boot test::the web UI never answered within 3 minutes"
docker logs "$name" 2>&1 | tail -80
exit 1
