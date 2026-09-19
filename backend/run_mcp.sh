#!/usr/bin/env bash
cd "$(dirname "$0")"
exec ./.venv/bin/python -u mcp_server.py
