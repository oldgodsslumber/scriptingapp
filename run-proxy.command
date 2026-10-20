#!/bin/bash
# Double-clickable launcher: starts Foundry Local, loads the model, starts the
# CORS proxy and opens the Video Script Generator in your browser.
# Resolves its own directory so it works no matter where it's dropped.
cd "$(dirname "$0")" || exit 1

# The model to load. Change here if the team standardizes on a different one.
# (The app's Settings → Local → Model should name the same model.)
MODEL="${FOUNDRY_MODEL:-qwen3-14b}"

stop() { echo; echo "$1"; echo; read -n 1 -s -r -p "Press any key to close."; exit 1; }

command -v foundry >/dev/null 2>&1 || stop "Foundry Local isn't installed. Install it with:
  brew tap microsoft/foundrylocal && brew install foundrylocal"
command -v python3 >/dev/null 2>&1 || stop "python3 isn't available. Install Apple's command line tools with:
  xcode-select --install"

# Make sure the Foundry server is up (harmless if already running).
# --idle-timeout 0 keeps it from shutting itself down between generations;
# older CLIs don't know the flag, so fall back to a plain start.
echo "Starting Foundry Local server..."
foundry server start --idle-timeout 0 >/dev/null 2>&1 || foundry server start >/dev/null 2>&1 || true

# Load the model into memory. A fresh server start does NOT auto-load it, and
# requests fail with "Model is not loaded" until this runs. Safe to repeat.
# A model that was never downloaded can't load, so download it then (first
# time only -- qwen3-14b is several GB).
echo "Loading model '$MODEL' (first load can take ~30-60s)..."
if ! foundry model load "$MODEL"; then
  echo "Load failed -- downloading '$MODEL' first..."
  foundry model download "$MODEL" && foundry model load "$MODEL" \
    || echo "[!] Could not load '$MODEL'. Run 'foundry model list' to see what's available."
fi

# Open the app once the proxy is listening (it serves the app at /).
( sleep 2; open "http://127.0.0.1:8757/" ) &

echo "Starting Foundry Local CORS proxy..."
export FOUNDRY_DEFAULT_MODEL="$MODEL"
exec python3 ./foundry_cors_proxy.py
