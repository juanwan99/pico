#!/usr/bin/env bash
# pico#1270 · Daily pico backup, off this host → Google Drive (gdrive:pico-backup).
#
#   backup-pico.sh run     dump everything, upload, verify sizes, prune > KEEP_DAYS, clean local
#   backup-pico.sh drill   pull the newest backup and restore it into throwaway containers
#                          (--corrupt flips one byte first: proves a bad backup is stopped;
#                           CORRUPT_CAUGHT exits 0 and leaves the real drill status alone)
#   backup-pico.sh watch   alert when the last good backup is older than STALE_HOURS (26)
#
# What goes out (one folder per run, <stamp>/):
#   mongo.archive.gz        LibreChat conversations (mongodump --archive --gzip)
#   pico.db.gz              runs / ledger (sqlite online backup, quick_check before upload)
#   pico-data.tgz           rest of the pico_data volume (sessions, memory; no *.bak* copies)
#   teacher-disks.tgz       teachers' own files
#   librechat-files.tgz     LibreChat uploads + images
#   meili.dump              Meilisearch dump with vectors (a rebuild would re-embed the whole KB)
#   SHA256SUMS
# Never restores onto live. Fails closed: status JSON + mail alert.
set -euo pipefail

REMOTE="${PICO_BACKUP_REMOTE:-gdrive:pico-backup}"
PROXY="${PICO_BACKUP_PROXY:-http://127.0.0.1:7893}"
KEEP_DAYS="${PICO_BACKUP_KEEP_DAYS:-15}"
WORK="${PICO_BACKUP_WORK:-$HOME/var/pico-backup-work}"
LOG_DIR="${PICO_BACKUP_LOG_DIR:-$HOME/logs}"
STATUS_JSON="${PICO_BACKUP_STATUS_JSON:-$LOG_DIR/pico-backup-status.json}"
ALERT_BIN="${PICO_BACKUP_ALERT:-$HOME/scripts/edu-backup-alert.py}"
PICO_ENV="${PICO_BACKUP_ENV:-/opt/pico/.env}"
API="${PICO_BACKUP_API_CONTAINER:-pico-pico-api-1}"
MONGO="${PICO_BACKUP_MONGO_CONTAINER:-pico-mongo-1}"
MEILI="${PICO_BACKUP_MEILI_CONTAINER:-pico-meilisearch-1}"
LIBRECHAT="${PICO_BACKUP_LIBRECHAT_CONTAINER:-pico-librechat-1}"
RCLONE_BIN="${PICO_BACKUP_RCLONE:-rclone}"
RETRY_MAX="${PICO_BACKUP_RETRY_MAX:-6}"
STALE_HOURS="${PICO_BACKUP_STALE_HOURS:-26}"
# The proxy drops a single upload after ~10 min (~250–500 MB at its speed) and
# rclone then restarts the whole file. Parts this size each finish in a couple of minutes.
PART_MB="${PICO_BACKUP_PART_MB:-128}"

umask 077
mkdir -p "$WORK" "$LOG_DIR"

log() { printf '%s %s\n' "$(date -Iseconds)" "$*" >&2; }

write_status() {
  python3 - "$STATUS_JSON" "$1" "${2:-}" <<'PY'
import datetime, json, os, sys
path, state, msg = sys.argv[1:4]
now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
data = {}
if os.path.isfile(path):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        data = {}
data.update(state=state, updated=now, detail=msg[:400])
data["last_ok" if state == "OK" else "last_fail"] = now
json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
PY
}

fail() {
  local why="$1"
  write_status FAIL "$why"
  if [[ -f "$ALERT_BIN" ]]; then
    python3 "$ALERT_BIN" --subject "[pico] 备份失败 $(hostname)" \
      --body "pico 每日备份失败：$why。看 $LOG_DIR/pico-backup.log 与 $STATUS_JSON。" >/dev/null 2>&1 || true
  fi
  log "FAIL $why"
  exit 1
}

rclone_cmd() {
  local n=0
  export https_proxy="$PROXY" http_proxy="$PROXY" HTTPS_PROXY="$PROXY" HTTP_PROXY="$PROXY"
  until "$RCLONE_BIN" --retries 3 --low-level-retries 10 --retries-sleep 20s \
      --contimeout 30s --timeout 300s --stats 0 "$@" 2>"$WORK/rclone.err"; do
    n=$((n + 1))
    [[ "$n" -ge "$RETRY_MAX" ]] && return 1
    log "rclone retry $n/$RETRY_MAX"
    sleep 60
  done
}

nonempty() { [[ -s "$1" ]] || fail "empty $(basename "$1")"; }

meili_key() { grep -E '^MEILI_MASTER_KEY=' "$PICO_ENV" | tail -1 | cut -d= -f2-; }

# Meilisearch dump through its own API, from inside the api container (it reads PICO_MEILI_URL).
dump_meili() {
  local out="$1" key uid
  key="$(meili_key)"
  [[ -n "$key" ]] || fail "MEILI_MASTER_KEY missing"
  # -e K without a value: docker copies it from our env, so the key is not on the command line.
  uid="$(K="$key" docker exec -i -e K "$API" python3 - <<'PY'
import json, os, time, urllib.request
base, key = os.environ.get("PICO_MEILI_URL") or "http://127.0.0.1:7700", os.environ["K"]
def call(method, path):
    req = urllib.request.Request(base + path, method=method, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)
task = call("POST", "/dumps")["taskUid"]
for _ in range(600):
    t = call("GET", f"/tasks/{task}")
    if t["status"] in ("succeeded", "failed", "canceled"):
        break
    time.sleep(2)
if t["status"] != "succeeded":
    raise SystemExit(f"dump {t['status']}")
print(t["details"]["dumpUid"])
PY
)" || fail "meili dump"
  docker exec "$MEILI" cat "/meili_data/dumps/$uid.dump" >"$out" || fail "meili dump copy"
  docker exec "$MEILI" rm -f "/meili_data/dumps/$uid.dump" || true
  nonempty "$out"
}

cmd_run() {
  exec 9>"$WORK/run.lock"
  flock -n 9 || fail "another run holds the lock"
  curl -sS -o /dev/null --max-time 8 -x "$PROXY" https://www.googleapis.com/ || fail "proxy ${PROXY} cannot reach googleapis"
  local stamp dir
  stamp="$(date +%Y%m%dT%H%M%S%z)"
  dir="$WORK/$stamp"
  mkdir -p "$dir"
  trap 'rm -rf "$dir"' EXIT

  log "mongo"
  docker exec "$MONGO" mongodump --archive --gzip --quiet >"$dir/mongo.archive.gz" || fail "mongodump"
  nonempty "$dir/mongo.archive.gz"

  log "pico.db"
  docker exec "$API" python3 -c '
import sqlite3
src = sqlite3.connect("file:/app/data/pico.db?mode=ro", uri=True)
dst = sqlite3.connect("/tmp/pico-backup.db")
src.backup(dst)
ok = dst.execute("pragma quick_check").fetchone()[0]
dst.close()
raise SystemExit(0 if ok == "ok" else "quick_check: " + ok)
' || fail "pico.db backup"
  docker exec "$API" cat /tmp/pico-backup.db | gzip -1 >"$dir/pico.db.gz" || fail "pico.db copy"
  docker exec "$API" rm -f /tmp/pico-backup.db || true
  nonempty "$dir/pico.db.gz"

  log "pico-data / teacher-disks / librechat files"
  docker exec "$API" tar -C /app/data --exclude='./pico.db' --exclude='./pico.db-*' \
    --exclude='./*.bak*' -czf - . >"$dir/pico-data.tgz" || fail "pico-data tar"
  docker exec "$API" tar -C /var/lib/pico/teacher-disks -czf - . >"$dir/teacher-disks.tgz" || fail "teacher-disks tar"
  docker exec "$LIBRECHAT" tar -C /app -czf - uploads client/public/images >"$dir/librechat-files.tgz" || fail "librechat tar"
  for f in pico-data.tgz teacher-disks.tgz librechat-files.tgz; do nonempty "$dir/$f"; done

  log "meili"
  dump_meili "$dir/meili.dump"

  (cd "$dir" && sha256sum -- * >SHA256SUMS)
  # Sums are of the whole files; big ones go up as NAME.part-000, -001, … (drill joins them).
  local f
  for f in "$dir"/*; do
    [[ "$(basename "$f")" == SHA256SUMS ]] && continue
    if [[ "$(stat -c %s "$f")" -gt $((PART_MB * 1048576)) ]]; then
      split -b "${PART_MB}M" -d -a 3 "$f" "$f.part-" && rm -f "$f"
    fi
  done
  log "upload $(du -sh "$dir" | cut -f1) → $REMOTE/$stamp"
  rclone_cmd copy "$dir" "$REMOTE/$stamp" || fail "upload (see $WORK/rclone.err)"
  # Off-host means the remote has every file at the right size.
  rclone_cmd check "$dir" "$REMOTE/$stamp" --size-only --one-way || fail "remote size check"
  rclone_cmd delete "$REMOTE" --min-age "${KEEP_DAYS}d" --drive-use-trash=false || log "prune skipped"
  rclone_cmd rmdirs "$REMOTE" --leave-root || true
  write_status OK "$stamp $(du -sb "$dir" | cut -f1) bytes"
  log "OK $stamp"
}

# Restore drill: newest backup → throwaway containers, no network, nothing live touched.
# Every check fails the drill (status JSON + mail); only a clean pass prints DRILL_OK.
DRILL_STATUS="${PICO_BACKUP_DRILL_STATUS:-$LOG_DIR/pico-backup-drill-status.json}"

# --corrupt is a probe of the drill itself: it never touches the real drill status
# (watch and pico_ops_watch read it) and only mails when the bad backup got through.
CORRUPT=""  # "" | armed (asked, byte not flipped yet) | flipped

drill_alert() {
  STATUS_JSON="$DRILL_STATUS" write_status FAIL "$1"
  if [[ -f "$ALERT_BIN" ]]; then
    python3 "$ALERT_BIN" --subject "[pico] 备份恢复演练失败 $(hostname)" \
      --body "pico 备份恢复演练失败：$1。看 $LOG_DIR/pico-backup.log。" >/dev/null 2>&1 || true
  fi
}

drill_fail() {
  if [[ "$CORRUPT" == flipped ]]; then
    log "CORRUPT_CAUGHT $1"  # the flipped byte was stopped: what --corrupt is meant to prove
    exit 0
  fi
  if [[ "$CORRUPT" == armed ]]; then
    log "CORRUPT_PROBE_ERROR $1"  # failed before the flip: proves nothing, status untouched
    exit 1
  fi
  drill_alert "$1"
  log "DRILL_FAIL $1"
  exit 1
}

cmd_drill() {
  local corrupt="${1:-}" latest dir img_api img_meili out n f part base
  [[ "$corrupt" == --corrupt ]] && CORRUPT=armed
  export https_proxy="$PROXY" HTTPS_PROXY="$PROXY"
  latest="$("$RCLONE_BIN" lsf "$REMOTE" --dirs-only 2>/dev/null | sort | tail -1)" || true
  latest="${latest%/}"
  [[ -n "$latest" ]] || drill_fail "no backup on $REMOTE"
  dir="$WORK/drill-$latest"
  rm -rf "$dir" && mkdir -p "$dir"
  trap 'rm -rf "$dir"; docker rm -f pico-drill-mongo pico-drill-meili >/dev/null 2>&1 || true' EXIT
  rclone_cmd copy "$REMOTE/$latest" "$dir" || drill_fail "download $latest"
  for part in "$dir"/*.part-000; do
    [[ -e "$part" ]] || continue
    base="${part%.part-000}"
    cat "$base".part-* >"$base" || drill_fail "join $(basename "$base")"
    rm -f "$base".part-*
  done
  if [[ "$corrupt" == --corrupt ]]; then
    printf '\xff' | dd of="$dir/mongo.archive.gz" bs=1 seek=1000 conv=notrunc status=none
    log "drill: flipped one byte of mongo.archive.gz on purpose"
    CORRUPT=flipped
  fi
  (cd "$dir" && sha256sum -c --quiet SHA256SUMS) || drill_fail "sha256 mismatch in $latest"
  log "drill $latest: sha256 ok"

  docker run -d --rm --name pico-drill-mongo --network none mongo:7 >/dev/null || drill_fail "start mongo"
  for _ in $(seq 1 30); do
    docker exec pico-drill-mongo mongosh --quiet --eval 'db.runCommand({ping:1}).ok' 2>/dev/null | grep -qx 1 && break
    sleep 2
  done
  docker exec -i pico-drill-mongo mongorestore --archive --gzip --quiet <"$dir/mongo.archive.gz" \
    || drill_fail "mongorestore"
  out="$(docker exec pico-drill-mongo mongosh --quiet LibreChat --eval \
    'const c = db.getCollectionNames().sort(); c.map(x => x + "=" + db[x].countDocuments()).join(" ")')" \
    || drill_fail "mongo count"
  [[ "$out" =~ conversations=[1-9] && "$out" =~ messages=[1-9] ]] || drill_fail "mongo empty: $out"
  log "drill mongo: $out"

  gunzip -c "$dir/pico.db.gz" >"$dir/pico.db" || drill_fail "gunzip pico.db"
  img_api="$(docker inspect -f '{{.Config.Image}}' "$API")"
  out="$(docker run --rm --network none -v "$dir/pico.db:/x.db:ro" "$img_api" python3 -c '
import sqlite3
c = sqlite3.connect("file:/x.db?mode=ro", uri=True)
qc = c.execute("pragma quick_check").fetchone()[0]
runs = c.execute("select count(*) from runs").fetchone()[0]
print("quick_check=%s runs=%d" % (qc, runs))
raise SystemExit(0 if qc == "ok" and runs > 0 else 1)')" || drill_fail "pico.db: ${out:-unreadable}"
  log "drill pico.db: $out"

  for f in pico-data.tgz teacher-disks.tgz librechat-files.tgz; do
    n="$(tar -tzf "$dir/$f" | wc -l)" || drill_fail "tar $f"
    [[ "$n" -gt 0 ]] || drill_fail "tar $f empty"
    log "drill $f: entries=$n"
  done

  img_meili="$(docker inspect -f '{{.Config.Image}}' "$MEILI")"
  docker run -d --rm --name pico-drill-meili --network none -v "$dir/meili.dump:/d.dump:ro" \
    "$img_meili" meilisearch --import-dump /d.dump --db-path /tmp/drill-db --master-key drill-only-key >/dev/null \
    || drill_fail "start meili"
  out=""
  # 72k documents took 9 min to import on 10-15; leave room for growth (30 min).
  for _ in $(seq 1 600); do
    out="$(docker exec pico-drill-meili sh -c 'wget -qO- http://127.0.0.1:7700/health' 2>/dev/null)" || true
    [[ "$out" == *available* ]] && break
    sleep 3
  done
  [[ "$out" == *available* ]] || drill_fail "meili import did not come up"
  out="$(docker exec pico-drill-meili sh -c 'wget -qO- --header "Authorization: Bearer drill-only-key" http://127.0.0.1:7700/stats' \
    | python3 -c 'import json,sys; s=json.load(sys.stdin)["indexes"]; print(" ".join("%s=%s" % (k, v["numberOfDocuments"]) for k, v in s.items())); raise SystemExit(0 if sum(v["numberOfDocuments"] for v in s.values()) else 1)')" \
    || drill_fail "meili empty: $out"
  log "drill meili: $out"
  if [[ -n "$CORRUPT" ]]; then
    drill_alert "--corrupt: a flipped byte in mongo.archive.gz passed every check"
    log "CORRUPT_MISSED $latest"
    exit 1
  fi
  STATUS_JSON="$DRILL_STATUS" write_status OK "$latest"
  log "DRILL_OK $latest"
}

# A run that never starts (timer off, host down, script gone) writes no FAIL: watch the age.
cmd_watch() {
  local verdict
  verdict="$(python3 - "$STATUS_JSON" "$STALE_HOURS" <<'PY'
import datetime, json, os, sys
path, hours = sys.argv[1], float(sys.argv[2])
now = datetime.datetime.now().astimezone()
data = json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else {}
ok = data.get("last_ok")
age = (now - datetime.datetime.fromisoformat(ok)).total_seconds() / 3600 if ok else None
if age is not None and age <= hours:
    print("FRESH %.1fh" % age)
    raise SystemExit
last_alert = data.get("last_stale_alert")
if last_alert and (now - datetime.datetime.fromisoformat(last_alert)).total_seconds() < 12 * 3600:
    print("STALE_ALERTED")  # one mail per 12 h, not one per hour
    raise SystemExit
data["last_stale_alert"] = now.isoformat(timespec="seconds")
json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
print("STALE " + ("never" if age is None else "%.1fh" % age))
PY
)"
  log "watch $verdict"
  if [[ "$verdict" == STALE\ * ]] && [[ -f "$ALERT_BIN" ]]; then
    python3 "$ALERT_BIN" --subject "[pico] 备份超过 ${STALE_HOURS} 小时没有成功 $(hostname)" \
      --body "pico 上次成功备份：${verdict#STALE }前。看 $LOG_DIR/pico-backup.log、$STATUS_JSON 和 systemctl --user status pico-backup.timer。" \
      >/dev/null 2>&1 || log "alert mail failed"
  fi
}

case "${1:-}" in
  run) cmd_run 2>&1 | tee -a "$LOG_DIR/pico-backup.log"; exit "${PIPESTATUS[0]}" ;;
  drill) cmd_drill "${2:-}" 2>&1 | tee -a "$LOG_DIR/pico-backup.log"; exit "${PIPESTATUS[0]}" ;;
  watch) cmd_watch 2>&1 | tee -a "$LOG_DIR/pico-backup.log" ;;
  *) echo "usage: $0 run|drill [--corrupt]|watch" >&2; exit 2 ;;
esac
