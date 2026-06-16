#!/bin/bash
LOG=/var/lib/murphy-production/observation_2026_06_15/cycle_log.txt
{
  echo "══ $(date -u +%H:%M:%S) ══"

  # R121 latest cycle
  R121=$(sudo journalctl -u murphy-inbound-autoresponse --since "6 minutes ago" --no-pager 2>&1 \
    | grep "R121 done" | tail -1)
  echo "  R121: ${R121##*python3*: }"

  # inbox depth
  N=$(ls /var/mail/vhosts/murphy.systems/cpost/new/ 2>/dev/null | wc -l)
  echo "  inbox: $N new"

  # health snapshot
  for ep in compliance shape_of_complete autonomy; do
    t0=$(date +%s%N)
    code=$(curl -sS -m 5 -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000/api/health/$ep" 2>/dev/null || echo TO)
    t1=$(date +%s%N)
    ms=$(( (t1 - t0) / 1000000 ))
    echo "  /$ep: $code (${ms}ms)"
  done

  # 402 count last 5 min
  c=$(sudo journalctl -u murphy-production --since "5 minutes ago" --no-pager 2>&1 \
    | grep -c "402 Client Error" 2>/dev/null || echo 0)
  echo "  402s: $c"
  echo ""
} >> $LOG 2>&1
