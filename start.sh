#!/bin/bash
# Start the Convey server using the correct Python interpreter.
# Hermes source modules require Python 3.11+ (hermes venv) for compiled extensions.

_find_hermes_python() {
    if [ -n "$HERMES_PYTHON" ]; then
        echo "$HERMES_PYTHON"
        return
    fi
    local hermes_bin
    hermes_bin=$(command -v hermes 2>/dev/null)
    if [ -n "$hermes_bin" ]; then
        # Extract venv hermes binary path from wrapper script, then derive python3
        local venv_hermes
        venv_hermes=$(grep -oP 'exec "\K[^"]+' "$hermes_bin" 2>/dev/null | head -1)
        if [ -n "$venv_hermes" ]; then
            local python
            python="$(dirname "$venv_hermes")/python3"
            if [ -x "$python" ]; then
                echo "$python"
                return
            fi
        fi
    fi
    echo "ERROR: Cannot find Hermes Python interpreter. Set HERMES_PYTHON or install Hermes." >&2
    return 1
}

PYTHON=$(_find_hermes_python) || exit 1
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR/user-portal"
exec "$PYTHON" server.py "$@"
