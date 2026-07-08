#!/usr/bin/env sh

CURRENT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export PYTHONPATH="$CURRENT_DIR${PYTHONPATH:+:$PYTHONPATH}"

if [ -x "$CURRENT_DIR/.venv/bin/python" ]; then
  exec "$CURRENT_DIR/.venv/bin/python" "$CURRENT_DIR/pipeline.py" "$@"
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run python "$CURRENT_DIR/pipeline.py" "$@"
fi

exec python3 "$CURRENT_DIR/pipeline.py" "$@"
