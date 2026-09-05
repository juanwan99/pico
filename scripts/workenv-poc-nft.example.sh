#!/usr/bin/env bash
# EXAMPLE only. Do not run on live pico.aivia.asia ECS.
# Publisher (a): DNAT $HOST_GW:18769 -> 127.0.0.1:18769 on br-pico-workenv.
# Policy accept. Never host-wide FORWARD policy drop.
echo "refusing to install nft from the example script" >&2
exit 4
