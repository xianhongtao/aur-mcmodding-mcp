#!/usr/bin/env python3
"""Offline MCP test: python smoke-test.py [--expected-version VERSION] [command [args ...]]."""
import argparse
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--expected-version')
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
expected_version = args.expected_version
if expected_version is None:
    recipe = (Path(__file__).resolve().parent / 'PKGBUILD').read_text()
    versions = re.findall(r'(?m)^pkgver=([^\n]+)$', recipe)
    if len(versions) != 1:
        parser.error('Cannot determine pkgver; pass --expected-version explicitly')
    expected_version = versions[0].strip("'\"")

with tempfile.TemporaryDirectory(prefix='mcmodding-aur-test-') as tmp:
    env = dict(os.environ, MCMODDING_SKIP_AUTO_UPDATE='1',
               MCMODDING_DATA_DIR=tmp, XDG_CACHE_HOME=tmp)
    with tempfile.TemporaryFile(mode='w+') as err:
        process = subprocess.Popen(args.command or ['/usr/bin/mcmodding-mcp'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=err, text=True, env=env)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)

        def send(message):
            process.stdin.write(json.dumps(message) + '\n')
            process.stdin.flush()

        def receive():
            if not selector.select(timeout=30):
                err.seek(0)
                raise TimeoutError('MCP reply timed out: ' + err.read())
            line = process.stdout.readline()
            if not line:
                err.seek(0)
                raise RuntimeError(err.read())
            return json.loads(line)

        try:
            send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
                'protocolVersion': '2024-11-05', 'capabilities': {},
                'clientInfo': {'name': 'aur-smoke-test', 'version': '1.0'}}})
            reply = receive()
            assert reply['id'] == 1 and 'result' in reply, reply
            assert reply['result']['serverInfo']['version'] == expected_version, reply
            print('initialize:', reply['result']['serverInfo'])
            send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}})
            reply = receive()
            assert reply['id'] == 2, reply
            names = {tool['name'] for tool in reply['result']['tools']}
            required = {'search_fabric_docs', 'get_example',
                        'explain_fabric_concept', 'get_minecraft_version'}
            assert required <= names, names
            print('tools/list:', ', '.join(sorted(names)))
            print('PASS (offline handshake only; no database/model downloads)')
        finally:
            selector.close()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
