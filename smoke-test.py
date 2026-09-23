#!/usr/bin/env python3
"""Offline MCP test: python smoke-test.py [command [args ...]]."""
import json
import os
import selectors
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix='mcmodding-aur-test-') as tmp:
    env = dict(os.environ, MCMODDING_SKIP_AUTO_UPDATE='1',
               MCMODDING_DATA_DIR=tmp, XDG_CACHE_HOME=tmp)
    with tempfile.TemporaryFile(mode='w+') as err:
        process = subprocess.Popen(sys.argv[1:] or ['/usr/bin/mcmodding-mcp'],
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
            assert reply['result']['serverInfo']['version'] == '0.5.0', reply
            print('initialize:', reply['result']['serverInfo'])
            send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}})
            reply = receive()
            assert reply['id'] == 2, reply
            names = {tool['name'] for tool in reply['result']['tools']}
            assert names == {'search_fabric_docs', 'get_example',
                             'explain_fabric_concept', 'get_minecraft_version'}, names
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
