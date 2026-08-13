#!/bin/bash
cd "$(dirname "$0")"
python3 -m http.server 5173 >/tmp/p1047_site.log 2>&1 &
PID=$!
sleep 1
open 'http://127.0.0.1:5173/person/P-1047/longitudinal-function/'
wait $PID
