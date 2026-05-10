#!/bin/bash
# 一宮市 給食レシピアプリ — ローカル起動スクリプト (macOS)
# ダブルクリックで実行できます。

cd "$(dirname "$0")/app"
PORT=8765
URL="http://localhost:$PORT/index.html"

echo "===================================="
echo " 一宮市 給食レシピアプリを起動します"
echo "===================================="
echo ""
echo "URL: $URL"
echo "終了するにはこのウィンドウで Ctrl+C を押してください。"
echo ""

# Open browser after a short delay
( sleep 1; open "$URL" ) &

# Start a simple Python static server
exec python3 -m http.server "$PORT" --bind 127.0.0.1
