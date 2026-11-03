#!/usr/bin/env bash
# Diagnose common permission and environment problems.
cd "$(dirname "$0")/.."

echo "── Project owner check ─────────────────────────────"
find . -not -user "$USER" -not -path "./.venv/*" -ls | head

echo
echo "── Directory permissions ───────────────────────────"
ls -la sessions/ profiles/ logs/ 2>&1

echo
echo "── Writable test ───────────────────────────────────"
for d in sessions profiles logs; do
  if [ -w "$d" ] && [ -x "$d" ]; then
    echo "   ✅ $d is writable"
  else
    echo "   ❌ $d is NOT writable — fix with:"
    echo "        sudo chown -R \$USER:\$USER $d"
    echo "        rm -rf $d/*"
  fi
done

echo
echo "── Stale X / VNC / websockify processes ────────────"
pgrep -a Xvfb 2>/dev/null || echo "   none"
pgrep -a x11vnc 2>/dev/null || echo "   none"
pgrep -a websockify 2>/dev/null || echo "   none"

echo
echo "── Stale X locks ───────────────────────────────────"
ls /tmp/.X*-lock 2>/dev/null || echo "   none"
