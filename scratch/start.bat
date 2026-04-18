#!/bin/bash
# Unigate starter
# Set token first: set TELEGRAM_BOT_TOKEN=your_token

python -m unigate start -f -c local.yaml -p 8080

# Then open in browser:
# http://localhost:8080/unigate/web/web
#
# Or use these endpoints:
# GET  /unigate/status
# GET  /unigate/web/web      (WebUI)
# POST /unigate/webhook/web (send to Telegram)