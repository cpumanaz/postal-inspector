#!/usr/bin/env bash
#
# cloudflare-ddns.sh — keep a set of Cloudflare A records pointed at this
# host's current public IPv4 address. Designed for a residential connection
# whose WAN IP can change (e.g. after a move or a lease renewal).
#
# Config is read from an env file (default: ~/.config/cloudflare-ddns/config.env)
# which must define:
#   CF_API_TOKEN   - Cloudflare token with "Edit zone DNS" on the zone
#   CF_ZONE_NAME   - e.g. example.com
#   CF_RECORDS     - space-separated record names to keep on the WAN IP
# Optional:
#   CF_TTL         - record TTL in seconds (default 60; 1 = "automatic")
#   CF_DRY_RUN     - "1" to log intended changes without applying them
#
# Exit codes: 0 = success (changed or already correct), 1 = error.

set -euo pipefail

CONFIG="${CF_DDNS_CONFIG:-$HOME/.config/cloudflare-ddns/config.env}"
API="https://api.cloudflare.com/client/v4"

log() { printf '%s ddns: %s\n' "$(date -Is)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

[ -r "$CONFIG" ] || die "config not readable: $CONFIG"
# shellcheck disable=SC1090
. "$CONFIG"

: "${CF_API_TOKEN:?CF_API_TOKEN missing in $CONFIG}"
: "${CF_ZONE_NAME:?CF_ZONE_NAME missing in $CONFIG}"
: "${CF_RECORDS:?CF_RECORDS missing in $CONFIG}"
CF_TTL="${CF_TTL:-60}"
CF_DRY_RUN="${CF_DRY_RUN:-0}"

command -v curl   >/dev/null || die "curl not found"
command -v python3 >/dev/null || die "python3 not found"

cf() {
  # cf METHOD PATH [DATA]
  local method="$1" path="$2" data="${3:-}"
  if [ -n "$data" ]; then
    curl -fsS --max-time 20 -X "$method" "$API$path" \
      -H "Authorization: Bearer $CF_API_TOKEN" \
      -H "Content-Type: application/json" --data "$data"
  else
    curl -fsS --max-time 20 -X "$method" "$API$path" \
      -H "Authorization: Bearer $CF_API_TOKEN" \
      -H "Content-Type: application/json"
  fi
}

jget() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)"; }

# --- discover current public IPv4 ---
get_public_ip() {
  local ip
  for url in https://api.ipify.org https://ifconfig.me https://icanhazip.com; do
    ip="$(curl -4 -fsS --max-time 10 "$url" 2>/dev/null | tr -d '[:space:]')" || true
    if printf '%s' "$ip" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$'; then
      printf '%s' "$ip"; return 0
    fi
  done
  return 1
}

PUBLIC_IP="$(get_public_ip)" || die "could not determine public IPv4"
log "public IP: $PUBLIC_IP"

# --- resolve zone id ---
ZONE_ID="$(cf GET "/zones?name=$CF_ZONE_NAME" | jget "['result'][0]['id']")" \
  || die "could not resolve zone id for $CF_ZONE_NAME"

changed=0

# ensure_record NAME TARGET_IP — make the A record NAME point at TARGET_IP
ensure_record() {
  local name="$1" target="$2"
  local rec rid cur
  rec="$(cf GET "/zones/$ZONE_ID/dns_records?type=A&name=$name")"
  rid="$(printf '%s' "$rec" | jget "['result'][0]['id']"      2>/dev/null || true)"
  cur="$(printf '%s' "$rec" | jget "['result'][0]['content']" 2>/dev/null || true)"

  if [ -z "$rid" ] || [ "$rid" = "None" ]; then
    log "WARN: no A record for $name (skipping; create it in Cloudflare first)"
    return 0
  fi
  if [ "$cur" = "$target" ]; then
    log "ok: $name already $target"
    return 0
  fi
  if [ "$CF_DRY_RUN" = "1" ]; then
    log "DRY-RUN would update $name: $cur -> $target"
    changed=1
    return 0
  fi
  local payload
  payload="$(python3 -c "import json,sys;print(json.dumps({'type':'A','name':sys.argv[1],'content':sys.argv[2],'ttl':int(sys.argv[3]),'proxied':False}))" "$name" "$target" "$CF_TTL")"
  if cf PUT "/zones/$ZONE_ID/dns_records/$rid" "$payload" >/dev/null; then
    log "updated $name: $cur -> $target"
    changed=1
  else
    die "failed to update $name"
  fi
}

# WAN-tracking records: follow this site's public IP
for name in $CF_RECORDS; do
  ensure_record "$name" "$PUBLIC_IP"
done

# Static records (LAN-internal): "name=ip name=ip ..." — kept at fixed targets
for pair in ${CF_STATIC_RECORDS:-}; do
  ensure_record "${pair%%=*}" "${pair#*=}"
done

[ "$changed" -eq 1 ] && log "done (records changed)" || log "done (no changes)"
exit 0
