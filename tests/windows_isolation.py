"""Native verification of the Windows command boundary, using disposable test data."""

import asyncio
import os
from pathlib import Path
import socket
import tempfile
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows AppContainer required')
class WindowsIsolation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from backend.windows_isolation import execute
        self.execute = execute
        self.system = Path(os.environ['SystemRoot']) / 'System32'
        self.cmd = str(self.system / 'cmd.exe')

    async def test_command_reads_staged_copy_but_cannot_open_host_file(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as folder:
            host = Path(folder) / 'sentinel.txt'
            host.write_text('private host data', encoding='utf-8')
            with patch.dict(os.environ, {'LUMINARIA_API_KEY': 'test-secret'}):
                command = f'type staged.txt & type "{host}" & if defined LUMINARIA_API_KEY echo unexpected'
                result = await self.execute([self.cmd, '/d', '/c', command], 10,
                                            inputs=[(Path('staged.txt'), b'isolated input')])
        self.assertIn('isolated input', result['stdout'], result)
        self.assertNotIn('private host data', result['stdout'], result)
        self.assertNotIn('unexpected', result['stdout'], result)

    async def test_localhost_connection_is_denied(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            url = f'http://127.0.0.1:{listener.getsockname()[1]}/'
            result = await self.execute(
                [str(self.system / 'curl.exe'), '--noproxy', '*', '--max-time', '3', url], 10
            )
            self.assertIn(result['exit_code'], (7, 28), result)
            listener.setblocking(False)
            with self.assertRaises(BlockingIOError):
                listener.accept()

    async def test_settings_self_check_verifies_staged_input_and_network_isolation(self):
        from unittest.mock import patch
        from httpx import ASGITransport, AsyncClient
        from backend.app import app

        port = os.environ.get('STUDIO_PORT', '3210')
        async with AsyncClient(transport=ASGITransport(app=app), base_url=f'http://127.0.0.1:{port}') as client:
            path = '/api/settings/command-sandbox/check'
            self.assertEqual((await client.post(path)).status_code, 403)
            boot = (await client.get('/api/bootstrap')).raise_for_status().json()
            with patch('backend.identity.required', return_value=False):
                response = await client.post(path, headers={'X-Studio-Token': boot['token']})
        result = response.raise_for_status().json()
        self.assertTrue(result['passed'], result)

    async def test_windows_powershell_starts_in_isolated_workspace(self):
        from backend.windows_isolation import powershell_command
        result = await self.execute(
            powershell_command('Get-Content input.txt'), 15,
            inputs=[(Path('input.txt'), b'PowerShell is isolated')],
        )
        self.assertEqual(result['exit_code'], 0, result)
        self.assertIn('PowerShell is isolated', result['stdout'], result)

    async def test_timeout_cleans_up_a_running_process(self):
        result = await self.execute([self.cmd, '/d', '/c', 'for /L %n in (1,0,2) do @rem waiting'], 1)
        self.assertTrue(result['timed_out'], result)

    async def test_windows_powershell_captures_native_child_output(self):
        from backend.windows_isolation import powershell_command
        result = await self.execute(powershell_command("cmd.exe /d /c 'echo nested'"), 15)
        self.assertEqual(result['exit_code'], 0, result)
        self.assertIn('nested', result['stdout'], result)

    async def test_python_can_run_from_the_portable_bundle(self):
        from backend.config import bundled_runtime
        from backend.windows_isolation import powershell_command
        executable = os.environ.get('LUMINARIA_TEST_PORTABLE_PYTHON') or bundled_runtime('python')
        if not executable:
            self.skipTest('Luminaria portable runtime is not installed')
        result = await self.execute(powershell_command("python -c 'print(456)'"), 15, python_bundle=executable)
        self.assertEqual(result['exit_code'], 0, result)
        self.assertIn('456', result['stdout'], result)
        failed = await self.execute(powershell_command("python -c 'raise SystemExit(7)'"), 15, python_bundle=executable)
        self.assertEqual(failed['exit_code'], 7, failed)

    async def test_command_tool_uses_the_offline_workspace_and_reports_input_evidence(self):
        from hashlib import sha256
        from unittest.mock import patch
        from backend.config import CONFIG
        from backend.tools import Toolbox

        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'fixture.txt').write_bytes(b'verify this copy')
            with patch.dict(CONFIG, {'workspace': folder, 'external_tools': True}):
                result = await Toolbox(None, {}).dispatch(
                    'run_command', {'command': 'Get-Content fixture.txt', 'inputs': ['fixture.txt']}, {}
                )
        self.assertEqual(result['exit_code'], 0, result)
        self.assertIn('verify this copy', result['stdout'])
        self.assertEqual(result['input_evidence'], {'fixture.txt': sha256(b'verify this copy').hexdigest()})
