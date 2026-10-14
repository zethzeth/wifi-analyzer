import argparse

parser = argparse.ArgumentParser(prog='kestrel', description='Wi-Fi and connection analyzer')
parser.add_argument('command', nargs='?', default='run', choices=['run', 'channels', 'serve'],
                    help='run: interactive test (default); channels: channel-load scan; serve: JSON bridge for the app')
command = parser.parse_args().command

if command == 'serve':
    from kestrel.bridge import serve
    serve()
else:
    from kestrel import cli
    cli.run() if command == 'run' else cli.channels_view()
