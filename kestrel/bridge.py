# JSON-lines protocol for the Electron app: commands arrive on stdin, events leave on stdout.
# → {"cmd": "connection"} | {"cmd": "scan", "rescan": true} | {"cmd": "start", "settings": {...}} | {"cmd": "stop"}
# ← {"event": "<name>", "data": {...}}
import json
import sys
import threading
import traceback

from kestrel import channels, platforms
from kestrel.runner import Analysis
from kestrel.settings import Settings

_out = sys.stdout
_lock = threading.Lock()


def emit(event: str, data: dict):
    with _lock:
        _out.write(json.dumps({'event': event, 'data': data}) + '\n')
        _out.flush()


def serve():
    sys.stdout = sys.stderr  # Stray prints from libraries must not corrupt the protocol
    analysis: Analysis | None = None

    def run_test(settings: dict):
        nonlocal analysis
        try:
            analysis = Analysis(Settings(**settings), platforms.connection(), emit)
            analysis.run()
        finally:
            analysis = None
            emit('idle', {})

    def scan(rescan: bool):
        connection = platforms.connection()
        emit('channels', channels.analyse(platforms.networks(rescan=rescan), connection.link))

    commands = {
        'connection': lambda cmd: emit('connection', platforms.connection().to_dict()),
        'scan': lambda cmd: scan(cmd.get('rescan', False)),
        'start': lambda cmd: analysis is None and run_test(cmd.get('settings', {})),
        'stop': lambda cmd: analysis and analysis.stop(),
    }

    emit('ready', {'platform': sys.platform})
    for line in sys.stdin:
        try:
            cmd = json.loads(line)
            handler = commands[cmd['cmd']]
        except (ValueError, KeyError):
            emit('error', {'message': f'Bad command: {line.strip()}'})
            continue
        threading.Thread(target=_guarded, args=(handler, cmd), daemon=True).start()


def _guarded(handler, cmd: dict):
    try:
        handler(cmd)
    except Exception as e:
        traceback.print_exc()
        emit('error', {'message': f'{cmd["cmd"]} failed: {e}'})
