#!/bin/bash
# T-PACK-TRIPLE-100-NIGHT (#461) 连跑：同 tip 五案连续各跑一遍 + 稳定连跑。
# Usage: bash scripts/lianpao-pack461.sh [round_label]
set -a
# shellcheck source=/dev/null
source /home/ops/pico/scripts/visual-gate-env.sh
set +a
cd /home/ops/pico
export NODE_PATH="$HOME/.npm-global/lib/node_modules${NODE_PATH:+:$NODE_PATH}"

ROUND="${1:-p4}"
CARD=pack-triple-100-night
EVID=/home/ops/pico/docs/evidence/$CARD

reset_api() {
  ssh -o BatchMode=yes -o ConnectTimeout=8 pico-prod '
    for c in pico-pico-api-1 pico-librechat-1 pico-mongo-1; do
      if ! sudo docker ps --format "{{.Names}}" | grep -qx "$c"; then
        sudo docker start "$c" >/dev/null 2>&1
      fi
    done
    sudo docker restart pico-pico-api-1 >/dev/null 2>&1
    sleep 5
    sudo sh -c "sync; echo 3 > /proc/sys/vm/drop_caches" >/dev/null 2>&1
  '
  for i in $(seq 1 20); do
    tip_ok=$(curl -sf -o /dev/null --max-time 4 https://pico.aivia.asia/api/pico/tip && echo y || echo n)
    login_ok=$(curl -s -o /dev/null -w "%{http_code}" --max-time 4 https://pico.aivia.asia/login)
    if [ "$tip_ok" = "y" ] && [ "$login_ok" = "200" ]; then
      echo "--- site up after ${i}x4s ---"
      return 0
    fi
    sleep 4
  done
  echo "--- site NOT up after heal ---"
  return 1
}

run_case() {
  local k="$1" scene="$2" prompt="$3" model="${4:-}" skip_v3="${5:-}"
  echo "===== $ROUND/$k start $(date -u +%H:%M:%S) ====="
  local model_args=() v3_args=()
  [ -n "$model" ] && model_args=(--model "$model")
  [ "$skip_v3" = "1" ] && v3_args=(--skip-v3)
  node scripts/visual-gate.mjs \
    --card "$CARD" --scene "$scene" \
    --out "$EVID/$scene" \
    --timeout-ms 420000 --prompt "$prompt" "${model_args[@]}" "${v3_args[@]}" \
    > "/tmp/lp-$ROUND-$k.log" 2>&1
  local code=$?
  python3 -c "
import json
try:
  d=json.load(open('$EVID/$scene/manifest.json'))
  print('$k conv:', d['conversation_url'].split('/')[-1].split('?')[0], 'mono:', d.get('monologue_clean'), 'v3:', d.get('v3_human_page'), 'eligible:', d.get('scene_visual_pass_eligible'), 'frames:', d.get('missing_frames'))
except Exception as e:
  print('$k manifest ERR', e)
"
  return "$code"
}

run_followup() {
  local k="$1" scene="$2" conv="$3" prompt="$4"
  echo "===== $ROUND/$k v2 start $(date -u +%H:%M:%S) ====="
  node scripts/ds5-followup.mjs --conv "$conv" --out "$EVID/$scene" --prompt "$prompt" > "/tmp/lp-$ROUND-$k-v2.log" 2>&1
  local code=$?
  echo "v2 exit=$code"
  return "$code"
}

P1='请做一页「孟德尔遗传定律」互动 HTML 课件，精致一点，可下载可打开；要有清晰图示或交互，不要系统侧自检墙。'
P2='请交付至少 5 个独立可下载文件且数字互相一致：①项目一页纸.md ②里程碑.csv ③风险清单.md ④周报模板.md ⑤给老板的3句口头汇报.txt。预算48万、周期6周、团队7人。不要系统侧自检墙。'
P3='做一页周末市集摊位菜单（HTML或MD），4个品名与价格，可下载。'
P3V2='改成 v2：所有价格上调10%，并加一个「季节限定」品项，重新交付。'
P4='请把会议室预约做成可在微信里直接用的小程序工程，并导入微信开发者工具、生成体验版二维码。做不到请明确说不能做什么，不要假装已上线。'
P5='今天天气怎么样？随便聊聊就行，不需要文件。'

FAIL=0
run_case c1 "$ROUND-c1-mendel" "$P1" pico-agent || FAIL=1
run_case c2 "$ROUND-c2-multifile" "$P2" pico-agent 1 || FAIL=1
if run_case c3 "$ROUND-c3-edit" "$P3" pico-agent 1; then
  C3_CONV=$(python3 -c "import json;print(json.load(open('$EVID/$ROUND-c3-edit/manifest.json'))['conversation_url'].split('/')[-1].split('?')[0])")
  run_followup c3 "$ROUND-c3-edit" "$C3_CONV" "$P3V2" || FAIL=1
else
  FAIL=1
fi
run_case c4 "$ROUND-c4-boundary" "$P4" "" 1 || FAIL=1
run_case c5 "$ROUND-c5-chat" "$P5" "" 1 || FAIL=1

echo "===== LIANPAO DONE $ROUND $(date -u +%H:%M:%S) FAIL=$FAIL ====="
exit "$FAIL"
