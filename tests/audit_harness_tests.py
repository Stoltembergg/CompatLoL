# SPDX-License-Identifier: GPL-3.0-only
import importlib.util
import json
import os
import re
from pathlib import Path
import signal
import struct
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('audit_linux', ROOT / 'tools/audit_linux.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class FakeRunner:
    def __init__(self, texts=None, failure=None):
        self.calls, self.texts, self.failure = [], texts or {}, failure

    def run(self, name, argv, cwd, env, timeout):
        self.calls.append((name, list(argv), str(cwd), dict(env), timeout))
        return audit.phase(name, 'failed' if self.failure == name else 'passed',
                           'NONZERO_EXIT' if self.failure == name else 'OK', argv,
                           1 if self.failure == name else 0, stdout_path=name)

    def text(self, record):
        return self.texts.get(record['name'], '')


def check_schema(value, schema, document):
    """Exercise only the JSON Schema keywords used by this repository's audit schema."""
    if '$ref' in schema:
        target = document
        for component in schema['$ref'][2:].split('/'):
            target = target[component]
        return check_schema(value, target, document)
    types = {'object': lambda v: isinstance(v, dict), 'array': lambda v: isinstance(v, list),
             'string': lambda v: isinstance(v, str), 'integer': lambda v: type(v) is int,
             'null': lambda v: v is None}
    if 'type' in schema:
        expected = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        assert any(types[kind](value) for kind in expected), (value, schema['type'])
    if 'const' in schema:
        assert value == schema['const']
    if 'enum' in schema:
        assert value in schema['enum']
    if isinstance(value, str) and 'pattern' in schema:
        assert re.search(schema['pattern'], value)
    if type(value) is int and 'minimum' in schema:
        assert value >= schema['minimum']
    if isinstance(value, list):
        assert len(value) >= schema.get('minItems', 0)
        if 'items' in schema:
            for item in value:
                check_schema(item, schema['items'], document)
    if isinstance(value, dict):
        assert set(schema.get('required', [])) <= set(value)
        properties = schema.get('properties', {})
        extra = schema.get('additionalProperties', True)
        for key, item in value.items():
            if key in properties:
                check_schema(item, properties[key], document)
            elif extra is False:
                raise AssertionError('unexpected field ' + key)
            elif isinstance(extra, dict):
                check_schema(item, extra, document)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.cfg = audit.load_config(ROOT / 'config/audit-linux.json')

    def tearDown(self):
        self.temp.cleanup()

    def assertCode(self, code, function, *args):
        with self.assertRaises(audit.AuditError) as error:
            function(*args)
        self.assertEqual(error.exception.code, code)

    def test_non_linux_never_runs_subprocess(self):
        runner = FakeRunner()
        host = {'os': 'Darwin', 'arch': 'x86_64', 'distribution': {'id': None, 'version_id': None}}
        report = audit.execute(self.root, self.cfg, ROOT / 'config/audit-linux.json', self.root,
                               'run', host=host, runner=runner)
        self.assertEqual(report['status'], 'blocked')
        self.assertIsNone(report['baseline_llvm_major'])
        self.assertEqual(len(report['candidates']), 2)
        self.assertTrue(all(item['status'] == 'blocked' for item in report['candidates']))
        self.assertEqual(runner.calls, [])

    def test_blocked_report_matches_repository_schema(self):
        host = {'os': 'Darwin', 'arch': 'x86_64', 'distribution': {'id': None, 'version_id': None}}
        report = audit.execute(self.root, self.cfg, ROOT / 'config/audit-linux.json', self.root, 'run', host=host, runner=FakeRunner())
        schema = json.loads((ROOT / 'schemas/audit-run-v1.schema.json').read_text())
        check_schema(report, schema, schema)
        report['baseline_llvm_major'] = 999
        with self.assertRaises(AssertionError):
            check_schema(report, schema, schema)

    def test_missing_tools_are_blocked(self):
        runner = FakeRunner()
        host = {'os': 'Linux', 'arch': 'x86_64', 'distribution': {'id': 'ubuntu', 'version_id': '24.04'}}
        with patch.object(audit.shutil, 'which', return_value=None):
            report = audit.execute(self.root, self.cfg, ROOT / 'config/audit-linux.json', self.root,
                                   'run', host=host, runner=runner)
        self.assertEqual(report['status'], 'blocked')
        self.assertEqual(report['candidates'][0]['phases'][0]['code'], 'TOOLS_MISSING')
        self.assertEqual(runner.calls, [])

    def test_distribution_arch_and_major_refused(self):
        runner = FakeRunner()
        for host, code in [({'os': 'Linux', 'arch': 'aarch64', 'distribution': {}}, 'LINUX_X86_64_REQUIRED'),
                           ({'os': 'Linux', 'arch': 'x86_64', 'distribution': {'id': 'debian'}}, 'UBUNTU_24_04_REQUIRED')]:
            report = audit.execute(self.root, self.cfg, ROOT / 'config/audit-linux.json', self.root, 'run', host=host, runner=runner)
            self.assertEqual(report['candidates'][0]['phases'][0]['code'], code)
        self.assertCode('LLVM_MAJOR_NOT_CONFIGURED', audit.execute, self.root, self.cfg,
                        ROOT / 'config/audit-linux.json', self.root, 'run', 21)

    def test_config_rejects_gpu_bool_and_invalid_limits(self):
        for key, value in [('schema_version', True), ('execute_gpu', True), ('jobs', True), ('llvm_candidates', [14, 14]), ('compiler_major', 21)]:
            cfg = dict(self.cfg)
            cfg[key] = value
            path = self.root / 'config.json'
            path.write_text(json.dumps(cfg))
            with self.assertRaises(audit.AuditError):
                audit.load_config(path)

    def test_output_new_inside_results_no_symlinks(self):
        path = self.root / '.work/results/new'
        self.assertEqual(audit.new_output(self.root, path), path)
        with self.assertRaises(FileExistsError):
            audit.new_output(self.root, path)
        self.assertCode('OUTPUT_OUTSIDE_RESULTS', audit.new_output, self.root, self.root / 'outside')
        (self.root / '.work/results/link').symlink_to(path, target_is_directory=True)
        self.assertCode('OUTPUT_SYMLINK', audit.new_output, self.root, self.root / '.work/results/link/child')

    def test_source_revision_and_dirt_refused(self):
        source = self.root / '.work/upstream/indium'
        (source / '.git').mkdir(parents=True)
        (self.root / 'third_party').mkdir()
        (self.root / 'third_party/sources.lock.json').write_text(json.dumps({'sources': [
            {'url': 'https://github.com/darlinghq/indium.git', 'revision': 'a' * 40, 'gitlinks': []}]}))
        mismatch = FakeRunner({'source-revision': 'b' * 40})
        self.assertCode('SOURCE_REVISION_MISMATCH', audit.check_sources, self.root, mismatch, {}, [])
        dirty = FakeRunner({'source-revision': 'a' * 40, 'source-clean': ' M CMakeLists.txt'})
        self.assertCode('SOURCE_DIRTY', audit.check_sources, self.root, dirty, {}, [])
        clean = FakeRunner({'source-revision': 'a' * 40})
        self.assertEqual(audit.check_sources(self.root, clean, {}, [])[0], source)

    def test_major_and_environment_separation(self):
        self.assertCode('LLVM_CONFIG_MAJOR_MISMATCH', audit.selected_major, '18.1.8', 14)
        audit.selected_major('14.0.6', 14)
        for major in (14, 18):
            env = audit.candidate_env(major, {'PATH': '/fake', 'LD_PRELOAD': 'evil', 'LD_LIBRARY_PATH': '/evil'})
            self.assertTrue(env['PATH'].startswith('/usr/lib/llvm-%d/bin:' % major))
            self.assertEqual(env['LLVM_DIR'], '/usr/lib/llvm-%d/lib/cmake/llvm' % major)
            self.assertNotIn('LD_PRELOAD', env)
            self.assertNotIn('LD_LIBRARY_PATH', env)

    def test_probe_missing_symbols_and_library_mismatch(self):
        data = {'schema_version': 1, 'missing_symbols': [], 'libraries': [str(self.root / 'libLLVM.so')], 'resolved_count': 2, 'symbol_count': 2, 'status': 'passed', 'code': 'OK'}
        audit.validate_probe(data, self.root / 'libLLVM.so')
        self.assertCode('LLVM_LIBRARY_MISMATCH', audit.validate_probe, data, self.root / 'other.so')
        data['missing_symbols'] = ['LLVMGetElementType']
        self.assertCode('LLVM_SYMBOLS_MISSING', audit.validate_probe, data, self.root / 'libLLVM.so')

    def test_spirv_and_reflection_validation(self):
        spv, reflection = self.root / 'shader.spv', self.root / 'shader.spv.json'
        reflection.write_text('{"function-infos":{"k@add_arrays":{}}}')
        for payload in (b'', b'\x03\x02\x23\x07', b'badmagic' * 3, struct.pack('<I', 0x07230203) + b'\0' * 17):
            spv.write_bytes(payload)
            with self.assertRaises(audit.AuditError):
                audit.validated_spirv(spv, reflection, 1024)
        spv.write_bytes(struct.pack('<5I', 0x07230203, 0x00010000, 0, 1, 0))
        audit.validated_spirv(spv, reflection, 1024)
        reflection.write_text('{"function-infos":{"bad":NaN}}')
        self.assertCode('REFLECTION_JSON_INVALID', audit.validated_spirv, spv, reflection, 1024)
        reflection.write_text('not JSON')
        self.assertCode('REFLECTION_JSON_INVALID', audit.validated_spirv, spv, reflection, 1024)
        reflection.write_text('{"function-infos":{}}')
        self.assertCode('REFLECTION_FUNCTIONS_MISSING', audit.validated_spirv, spv, reflection, 1024)

    def prepare_candidate(self):
        (self.root / 'config').mkdir()
        (self.root / 'config/audit-fixtures.json').write_text('{"schema_version":1,"approved":[]}')
        return FakeRunner({'llvm-package-versions': 'llvm-14 14.0.6 installed\nllvm-14-dev 14.0.6 installed',
                           'llvm-version': '14.0.6', 'llvm-library-name': 'libLLVM-14.so',
                           'llvm-library-directory': str(self.root), 'symbols': json.dumps({
                               'schema_version': 1, 'symbol_count': 2, 'resolved_count': 2,
                               'missing_symbols': [], 'libraries': [str(self.root / 'libLLVM-14.so')], 'status': 'passed', 'code': 'OK'})})

    def test_candidate_build_only_is_not_baseline(self):
        runner = self.prepare_candidate()
        with patch.object(audit.shutil, 'which', return_value='/usr/lib/llvm-14/bin/llvm-config'), patch.object(Path, 'is_file', return_value=True):
            result = audit.audit_candidate(self.root, self.root / 'source', 14, self.cfg, runner, 'synthetic', 'run', [])
        self.assertEqual(result['status'], 'build-only')
        self.assertIsNone(audit.baseline([result]))
        self.assertEqual(result['fixtures'][0]['code'], 'FIXTURE_PROVENANCE_UNCONFIRMED')
        self.assertFalse(any(name == 'translation' for name, *_ in runner.calls))
        configure = next(call for call in runner.calls if call[0] == 'configure')
        self.assertIn('-DLLVM_DIR=/usr/lib/llvm-14/lib/cmake/llvm', configure[1])
        self.assertTrue(any('/llvm-14/' in str(arg) for arg in configure[1]))

    def test_failed_spirv_val_never_establishes_baseline(self):
        runner = self.prepare_candidate()
        runner.failure = 'spirv-val'
        with patch.object(audit.shutil, 'which', return_value='/usr/lib/llvm-14/bin/llvm-config'), patch.object(Path, 'is_file', return_value=True), patch.object(audit, 'approved_fixtures', return_value=[(self.root / 'test.metallib', 'a' * 64)]), patch.object(audit, 'validated_spirv'):
            result = audit.audit_candidate(self.root, self.root / 'source', 14, self.cfg, runner, 'synthetic', 'run', [])
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(audit.baseline([result]))
        self.assertEqual(result['fixtures'][0]['status'], 'failed')

    def test_selected_llvm_packages_are_independent(self):
        runner = FakeRunner({'llvm-package-versions': 'llvm-18 18.1.8 installed\nllvm-18-dev 18.1.8 installed'})
        audit.query_packages(runner, ('llvm-18', 'llvm-18-dev'), self.root, {}, [], 'llvm-package-versions')
        self.assertNotIn('llvm-14', runner.calls[0][1])
        self.assertNotIn('llvm-14-dev', runner.calls[0][1])
        self.assertCode('DEVELOPMENT_PACKAGES_MISSING', audit.query_packages,
                        runner, ('llvm-14', 'llvm-14-dev'), self.root, {}, [], 'llvm-package-versions')

    def verified_candidate(self, major):
        candidate = audit.make_candidate(major)
        candidate['status'] = 'passed'
        candidate['phases'] = [audit.phase(name, 'passed', 'OK', exit_code=0) for name in audit.PHASES]
        candidate['fixtures'] = [{'sha256': 'a' * 64, 'status': 'passed', 'code': 'OK'}]
        return candidate

    def test_smallest_fully_passed_candidate_is_baseline(self):
        candidates = [self.verified_candidate(18), self.verified_candidate(14)]
        self.assertEqual(audit.baseline(candidates), 14)
        candidates[1]['status'] = 'build-only'
        self.assertEqual(audit.baseline(candidates), 18)

    def test_passed_label_without_complete_evidence_is_not_baseline(self):
        self.assertIsNone(audit.baseline([{'llvm_major': 14, 'status': 'passed'}]))
        for field in ('phases', 'fixtures'):
            candidate = self.verified_candidate(14)
            candidate[field] = []
            self.assertIsNone(audit.baseline([candidate]))
        candidate = self.verified_candidate(14)
        candidate['phases'][-1]['status'] = 'failed'
        self.assertIsNone(audit.baseline([candidate]))
        candidate = self.verified_candidate(14)
        candidate['fixtures'][0]['sha256'] = None
        self.assertIsNone(audit.baseline([candidate]))

    def test_corrupt_probe_output_keeps_failure_schema_valid(self):
        runner = self.prepare_candidate()
        runner.texts['symbols'] = json.dumps({'schema_version': 1, 'missing_symbols': 5})
        with patch.object(audit.shutil, 'which', return_value='/usr/lib/llvm-14/bin/llvm-config'), patch.object(Path, 'is_file', return_value=True):
            candidate = audit.audit_candidate(self.root, self.root / 'source', 14, self.cfg, runner, 'synthetic', 'run', [])
        self.assertEqual(candidate['status'], 'failed')
        self.assertEqual(candidate['missing_symbols'], [])
        schema = json.loads((ROOT / 'schemas/audit-run-v1.schema.json').read_text())
        check_schema(candidate, schema['$defs']['candidate'], schema)

    def test_both_candidates_use_distinct_builds_and_environments(self):
        first = self.prepare_candidate()
        second = FakeRunner(dict(first.texts))
        second.texts['llvm-package-versions'] = 'llvm-18 18.1.8 installed\nllvm-18-dev 18.1.8 installed'
        second.texts['llvm-version'] = '18.1.8'
        second.texts['llvm-library-name'] = 'libLLVM-18.so'
        second.texts['symbols'] = json.dumps({'schema_version': 1, 'symbol_count': 2, 'resolved_count': 2,
                                            'missing_symbols': [], 'libraries': [str(self.root / 'libLLVM-18.so')], 'status': 'passed', 'code': 'OK'})
        def which(name, path):
            return '/usr/lib/llvm-%d/bin/llvm-config' % (18 if path.startswith('/usr/lib/llvm-18/') else 14)
        with patch.object(audit.shutil, 'which', side_effect=which), patch.object(Path, 'is_file', return_value=True):
            for major, runner in ((14, first), (18, second)):
                result = audit.audit_candidate(self.root, self.root / 'source', major, self.cfg, runner, 'same-run', 'run', [])
                self.assertEqual(result['status'], 'build-only')
        commands = [next(call for call in runner.calls if call[0] == 'configure') for runner in (first, second)]
        builds = [command[1][command[1].index('-B') + 1] for command in commands]
        self.assertNotEqual(builds[0], builds[1])
        self.assertNotEqual(commands[0][3]['LLVM_DIR'], commands[1][3]['LLVM_DIR'])

    def test_runner_bounds_logs_and_timeout(self):
        runner = audit.Runner(self.root, 128)
        record = runner.run('flood', [sys.executable, '-c', 'import sys;sys.stdout.write("x"*20000);sys.stderr.write("y"*20000)'], self.root, os.environ.copy(), 5)
        self.assertEqual(record['status'], 'passed')
        for key in ('stdout_path', 'stderr_path'):
            data = (self.root / record[key]).read_bytes()
            self.assertLessEqual(len(data), 128 + len(b'\n[OUTPUT_TRUNCATED]\n'))
            self.assertIn(b'OUTPUT_TRUNCATED', data)
        started = __import__('time').monotonic()
        record = runner.run('timeout', [sys.executable, '-c', 'import time;time.sleep(30)'], self.root, os.environ.copy(), 0.1)
        self.assertEqual(record['code'], 'TIMEOUT')
        self.assertLess(__import__('time').monotonic() - started, 3)

    def test_log_preparation_failure_never_spawns(self):
        missing = self.root / 'missing-directory'
        runner = audit.Runner(missing, 128)
        with patch.object(audit.subprocess, 'Popen') as spawn:
            with self.assertRaises(OSError):
                runner.run('logs-fail', ['unused'], self.root, {}, 1)
            spawn.assert_not_called()

    def test_selector_failure_still_cleans_process(self):
        runner = audit.Runner(self.root, 128)
        process = MagicMock()
        process.pid = 1234
        process.stdout.closed = False
        process.stderr.closed = False
        with patch.object(audit.subprocess, 'Popen', return_value=process), patch.object(audit.selectors, 'DefaultSelector') as selector, patch.object(audit.os, 'set_blocking'), patch.object(audit.os, 'killpg') as kill:
            selector.return_value.__enter__.return_value.register.side_effect = OSError('synthetic selector failure')
            with self.assertRaises(OSError):
                runner.run('selector-fail', ['unused'], self.root, {}, 1)
            kill.assert_called_once_with(1234, signal.SIGKILL)
            process.wait.assert_called_once()
            process.stdout.close.assert_called_once()
            process.stderr.close.assert_called_once()

    def test_descendant_held_pipe_times_out(self):
        runner = audit.Runner(self.root, 128)
        program = 'import subprocess,sys;subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"])'
        record = runner.run('child-held-pipe', [sys.executable, '-c', program], self.root, os.environ.copy(), 0.2)
        self.assertEqual(record['code'], 'TIMEOUT')

    def test_one_failed_candidate_does_not_abort_other(self):
        runner = FakeRunner({'package-versions': '\n'.join(name + ' 1.0 installed' for name in audit.COMMON_PACKAGES)})
        host = {'os': 'Linux', 'arch': 'x86_64', 'distribution': {'id': 'ubuntu', 'version_id': '24.04'}}
        outcomes = [audit.make_candidate(14), audit.make_candidate(18)]
        outcomes[0]['status'] = 'failed'
        outcomes[1]['status'] = 'build-only'
        with patch.object(audit.shutil, 'which', return_value='/tools/tool'), patch.object(audit, 'check_sources', return_value=(self.root / 'source', {'indium': 'a' * 40})), patch.object(audit, 'audit_candidate', side_effect=outcomes) as candidate:
            report = audit.execute(self.root, self.cfg, ROOT / 'config/audit-linux.json', self.root, 'run', host=host, runner=runner)
        self.assertEqual(candidate.call_count, 2)
        self.assertEqual(report['status'], 'failed')
        self.assertIsNone(report['baseline_llvm_major'])

    def test_fixture_hash_and_path_refusals(self):
        source = self.root / 'source'
        (source / 'test').mkdir(parents=True)
        (self.root / 'config').mkdir()
        shader = source / 'test/synthetic.metallib'
        shader.write_bytes(b'MTLB-synthetic-test-only')
        approval = {'relative_path': 'test/synthetic.metallib', 'sha256': 'a' * 64,
                    'license': 'synthetic-test', 'origin': 'synthetic-test', 'evidence_ref': 'test-only'}
        policy = self.root / 'config/audit-fixtures.json'
        policy.write_text(json.dumps({'schema_version': 1, 'approved': [approval]}))
        self.assertCode('FIXTURE_HASH_MISMATCH', audit.approved_fixtures, self.root, source)
        approval['sha256'] = audit.sha256(shader)
        policy.write_text(json.dumps({'schema_version': 1, 'approved': [approval]}))
        self.assertEqual(audit.approved_fixtures(self.root, source)[0][0], shader)
        shader.unlink()
        shader.symlink_to(ROOT / 'config/audit-linux.json')
        self.assertCode('FIXTURE_PATH_REFUSED', audit.approved_fixtures, self.root, source)

    def test_bootstrap_fresh_clone_and_dirty_existing_checkout(self):
        import subprocess
        fixture = self.root / 'fixtures/synthetic.git'
        fixture.mkdir(parents=True)
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        def git(*args):
            return subprocess.run(['git', '-C', str(fixture), *args], env=env,
                                  check=True, capture_output=True, text=True).stdout.strip()
        git('init')
        (fixture / 'source.txt').write_text('open synthetic fixture\n')
        git('add', 'source.txt')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-m', 'Synthetic bootstrap regression')
        revision = git('rev-parse', 'HEAD')
        workspace = self.root / 'bootstrap-workspace'
        (workspace / 'tools').mkdir(parents=True)
        script = workspace / 'tools/bootstrap-test.sh'
        prefix = (ROOT / 'tools/bootstrap.sh').read_text().split('clone darling ')[0]
        script.write_text(prefix + '\nclone synthetic ' + revision + '\n')
        env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='url.' +
                   (self.root / 'fixtures').as_uri() + '/.insteadOf',
                   GIT_CONFIG_VALUE_0='https://github.com/darlinghq/', GIT_ALLOW_PROTOCOL='file')
        result = subprocess.run(['sh', str(script)], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        checkout = workspace / '.work/upstream/synthetic'
        self.assertEqual((checkout / 'source.txt').read_text(), 'open synthetic fixture\n')
        (checkout / 'source.txt').write_text('keep my local change\n')
        result = subprocess.run(['sh', str(script)], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Refusing dirty upstream synthetic', result.stderr)
        self.assertEqual((checkout / 'source.txt').read_text(), 'keep my local change\n')

    def test_provenance_unconfirmed_by_default(self):
        (self.root / 'config').mkdir()
        (self.root / 'config/audit-fixtures.json').write_text('{"schema_version":1,"approved":[]}')
        self.assertEqual(audit.approved_fixtures(self.root, self.root / 'source'), [])


if __name__ == '__main__':
    unittest.main()
