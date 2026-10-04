import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import re


REPO = Path(__file__).resolve().parents[1]
EXPECTED = re.search(r'(?m)^pkgver=([^\n]+)$', (REPO / 'PKGBUILD').read_text())[1].strip("'\"")
SERVER = '''import json, os, sys
assert os.environ['MCMODDING_SKIP_AUTO_UPDATE'] == '1'
assert os.path.isdir(os.environ['MCMODDING_DATA_DIR'])
for line in sys.stdin:
    request = json.loads(line)
    if request['method'] == 'initialize':
        result = {'serverInfo': {'name': 'fixture', 'version': os.environ['TEST_MCP_VERSION']}}
    elif request['method'] == 'tools/list':
        names = ['search_fabric_docs', 'get_example', 'explain_fabric_concept', 'get_minecraft_version', 'new_tool']
        if os.environ.get('TEST_MISSING_TOOL'):
            names.remove('get_example')
        result = {'tools': [{'name': name} for name in names]}
    else:
        continue
    print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'result': result}), flush=True)
'''


class SmokeTests(unittest.TestCase):
    def run_server(self, version, options=(), **env):
        with tempfile.TemporaryDirectory() as temporary:
            server = Path(temporary) / 'server.py'
            server.write_text(SERVER)
            return subprocess.run([sys.executable, str(REPO / 'tests' / 'smoke-test.py'), *options, sys.executable, str(server)],
                                  env=dict(os.environ, TEST_MCP_VERSION=version, **env), text=True, capture_output=True, timeout=15)

    def test_default_version_and_additional_tool(self):
        result = self.run_server(EXPECTED)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('new_tool', result.stdout)

    def test_explicit_version(self):
        result = self.run_server('0.6.0', ('--expected-version', '0.6.0'))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_version_and_missing_base_tool_fail(self):
        self.assertNotEqual(self.run_server('invalid-version').returncode, 0)
        self.assertNotEqual(self.run_server(EXPECTED, TEST_MISSING_TOOL='1').returncode, 0)


if __name__ == '__main__':
    unittest.main()
