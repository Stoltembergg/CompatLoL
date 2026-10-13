#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Non-privileged standalone Indium audit. Never launches Darling or a GPU demo."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import selectors
import shutil
import signal
import struct
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
PHASES = ('configure', 'build', 'probe-configure', 'probe-build', 'symbols', 'translation', 'spirv-val')
PACKAGES = ('build-essential', 'cmake', 'ninja-build', 'clang-18', 'llvm-14', 'llvm-14-dev',
            'llvm-18', 'llvm-18-dev', 'libvulkan-dev', 'libglfw3-dev', 'libglm-dev',
            'xxd', 'spirv-tools', 'python3', 'git', 'libssl-dev')
COMMON_PACKAGES = tuple(name for name in PACKAGES if not name.startswith('llvm-'))


class AuditError(Exception):
    def __init__(self, code, blocked=False):
        self.code, self.blocked = code, blocked
        super().__init__(code)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def strict_json(text):
    def reject_nonfinite(_):
        raise ValueError('NONFINITE_JSON')
    return json.loads(text, parse_constant=reject_nonfinite)


def load_config(path):
    cfg = strict_json(Path(path).read_text())
    required = {'schema_version', 'os_id', 'os_version', 'arch', 'llvm_candidates',
                'compiler_major', 'jobs', 'configure_timeout_seconds', 'build_timeout_seconds',
                'probe_timeout_seconds', 'translation_timeout_seconds', 'max_output_bytes',
                'enable_upstream_test_targets', 'execute_gpu'}
    if not isinstance(cfg, dict) or set(cfg) != required or type(cfg['schema_version']) is not int or cfg['schema_version'] != 1:
        raise AuditError('INVALID_CONFIG')
    if cfg['os_id'] != 'ubuntu' or cfg['os_version'] != '24.04' or cfg['arch'] != 'x86_64':
        raise AuditError('UNSUPPORTED_CONFIG_PLATFORM')
    candidates = cfg['llvm_candidates']
    if (not isinstance(candidates, list) or not candidates or
            any(type(n) is not int or n not in (14, 18) for n in candidates) or
            len(set(candidates)) != len(candidates)):
        raise AuditError('INVALID_LLVM_CANDIDATES')
    if cfg['compiler_major'] != 18 or type(cfg['compiler_major']) is not int:
        raise AuditError('INVALID_COMPILER')
    for key in ('jobs', 'configure_timeout_seconds', 'build_timeout_seconds',
                'probe_timeout_seconds', 'translation_timeout_seconds', 'max_output_bytes'):
        if type(cfg[key]) is not int or cfg[key] <= 0:
            raise AuditError('INVALID_CONFIG_LIMIT')
    if cfg['execute_gpu'] is not False or type(cfg['enable_upstream_test_targets']) is not bool:
        raise AuditError('GPU_EXECUTION_FORBIDDEN')
    return cfg


def new_output(root, directory):
    root = Path(root).resolve()
    requested = Path(os.path.abspath(directory))
    allowed = root / '.work/results'
    if requested == allowed or allowed not in requested.parents:
        raise AuditError('OUTPUT_OUTSIDE_RESULTS')
    for part in (requested, *requested.parents):
        if part.is_symlink():
            raise AuditError('OUTPUT_SYMLINK')
        if part == root:
            break
    requested.parent.mkdir(parents=True, exist_ok=True)
    requested.mkdir(mode=0o700)  # Existing paths are deliberately refused.
    return requested


def host_info():
    distribution = {'id': None, 'version_id': None}
    if platform.system() == 'Linux':
        try:
            for line in Path('/etc/os-release').read_text().splitlines():
                key, sep, value = line.partition('=')
                if sep and key in ('ID', 'VERSION_ID'):
                    distribution[key.lower()] = value.strip('"')
        except OSError:
            pass
    return {'os': platform.system(), 'arch': platform.machine(), 'distribution': distribution}


def phase(name, status, code, argv=(), exit_code=None, duration_ms=0, stdout_path=None, stderr_path=None):
    return {'name': name, 'status': status, 'code': code, 'argv': list(argv), 'exit_code': exit_code,
            'duration_ms': duration_ms, 'stdout_path': stdout_path, 'stderr_path': stderr_path}


class Runner:
    """Bounded pipe drains and process-group cleanup, including descendant-held pipes."""
    def __init__(self, output, cap):
        self.output, self.cap, self.counter = Path(output), cap, 0

    def run(self, name, argv, cwd, env, timeout):
        self.counter += 1
        label = '%03d-%s' % (self.counter, re.sub(r'[^a-zA-Z0-9_-]', '-', name))
        paths = [self.output / (label + '.stdout'), self.output / (label + '.stderr')]
        start = time.monotonic()
        timed_out = False
        truncated = [False, False]
        written = [0, 0]
        # Prepare log sinks before spawning; every operation after Popen is protected.
        with paths[0].open('xb') as stdout, paths[1].open('xb') as stderr, selectors.DefaultSelector() as selector:
            files = [stdout, stderr]
            try:
                process = subprocess.Popen(list(map(str, argv)), cwd=str(cwd), env=env,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           start_new_session=True)
            except OSError:
                return phase(name, 'blocked', 'PROCESS_START_FAILED', argv)
            deadline = start + timeout
            try:
                for index, pipe in enumerate((process.stdout, process.stderr)):
                    os.set_blocking(pipe.fileno(), False)
                    selector.register(pipe, selectors.EVENT_READ, index)
                while selector.get_map():
                    if time.monotonic() >= deadline:
                        timed_out = True
                        break
                    for key, _ in selector.select(min(0.1, max(0, deadline - time.monotonic()))):
                        try:
                            chunk = os.read(key.fileobj.fileno(), 65536)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                            continue
                        index = key.data
                        keep = max(0, self.cap - written[index])
                        files[index].write(chunk[:keep])
                        written[index] += min(len(chunk), keep)
                        truncated[index] |= len(chunk) > keep
                if not timed_out:
                    try:
                        process.wait(timeout=max(0.001, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        timed_out = True
            finally:
                # Also terminate children surviving their parent; never leave compiler groups behind.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                for pipe in (process.stdout, process.stderr):
                    if not pipe.closed:
                        pipe.close()
                for index, flag in enumerate(truncated):
                    if flag:
                        files[index].write(b'\n[OUTPUT_TRUNCATED]\n')
        code = 'TIMEOUT' if timed_out else ('OK' if process.returncode == 0 else 'NONZERO_EXIT')
        return phase(name, 'passed' if code == 'OK' else 'failed', code, argv,
                     process.returncode, int((time.monotonic() - start) * 1000),
                     paths[0].name, paths[1].name)

    def text(self, record):
        return (self.output / record['stdout_path']).read_text(errors='replace') if record['stdout_path'] else ''


def run_checked(runner, name, argv, cwd, env, timeout):
    item = runner.run(name, argv, cwd, env, timeout)
    if item['status'] != 'passed':
        raise AuditError('PREFLIGHT_' + item['code'], item['status'] == 'blocked')
    return runner.text(item).strip(), item


def check_sources(root, runner, env, tools):
    manifest = strict_json((root / 'third_party/sources.lock.json').read_text())
    entries = [entry for entry in manifest['sources'] if entry['url'].rstrip('/').endswith('/indium.git')]
    if len(entries) != 1:
        raise AuditError('INDIUM_MANIFEST_ENTRY_REQUIRED')
    entry = entries[0]
    source = root / '.work/upstream/indium'
    if not (source / '.git').exists():
        raise AuditError('SOURCE_MISSING_RUN_BOOTSTRAP', True)

    def verify(path, locked):
        actual, _ = run_checked(runner, 'source-revision', ['git', '-C', str(path), 'rev-parse', 'HEAD'], root, env, 30)
        if actual != locked['revision']:
            raise AuditError('SOURCE_REVISION_MISMATCH')
        dirty, _ = run_checked(runner, 'source-clean', ['git', '-C', str(path), 'status', '--porcelain', '--untracked-files=all'], root, env, 30)
        if dirty:
            raise AuditError('SOURCE_DIRTY')
        for link in locked.get('gitlinks', []):
            if 'source' not in link:
                raise AuditError('SOURCE_GITLINK_NOT_LOCKED')
            child = path / link['path']
            if not (child / '.git').exists():
                raise AuditError('SOURCE_GITLINK_MISSING', True)
            verify(child, link['source'])
    verify(source, entry)
    tools.append({'name': 'indium-source', 'version': entry['revision'], 'status': 'observed'})
    return source, {'indium': entry['revision']}


def candidate_env(major, env=None):
    result = dict(os.environ if env is None else env)
    prefix = '/usr/lib/llvm-%d' % major
    result['PATH'] = prefix + '/bin:' + result.get('PATH', '')
    result['LLVM_DIR'] = prefix + '/lib/cmake/llvm'
    # Never inherit search-path injection from a caller into the experiment.
    for key in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'CMAKE_PREFIX_PATH', 'LLVM_CONFIG'):
        result.pop(key, None)
    return result


def query_packages(runner, packages, root, env, tools, name='package-versions'):
    record = runner.run(name, ['dpkg-query', '-W', '-f=${binary:Package} ${Version} ${db:Status-Status}\n', *packages], root, env, 30)
    if record['status'] != 'passed':
        raise AuditError('DEVELOPMENT_PACKAGES_MISSING', True)
    versions = runner.text(record).strip()
    seen = set()
    for line in versions.splitlines():
        parts = line.split()
        if len(parts) != 3 or parts[2] != 'installed' or parts[0].split(':')[0] in seen:
            raise AuditError('DEVELOPMENT_PACKAGES_MISSING', True)
        seen.add(parts[0].split(':')[0])
        tools.append({'name': parts[0], 'version': parts[1], 'status': 'observed'})
    if seen != set(packages):
        raise AuditError('DEVELOPMENT_PACKAGES_MISSING', True)


def selected_major(version, expected):
    if not re.match(r'^%d(?:\.|$)' % expected, version):
        raise AuditError('LLVM_CONFIG_MAJOR_MISMATCH')


def validate_probe(data, expected_library):
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data.get('schema_version') != 1:
        raise AuditError('INVALID_PROBE_REPORT')
    missing = data.get('missing_symbols')
    if not isinstance(missing, list) or any(not isinstance(n, str) for n in missing):
        raise AuditError('INVALID_PROBE_REPORT')
    libraries = data.get('libraries')
    if not isinstance(libraries, list) or not libraries or any(not isinstance(lib, str) or not lib for lib in libraries):
        raise AuditError('LLVM_LIBRARY_NOT_IDENTIFIED')
    if type(data.get('resolved_count')) is not int or type(data.get('symbol_count')) is not int:
        raise AuditError('INVALID_PROBE_REPORT')
    if any(Path(lib).resolve() != Path(expected_library).resolve() for lib in libraries):
        raise AuditError('LLVM_LIBRARY_MISMATCH')
    if missing or data.get('resolved_count', 0) != data.get('symbol_count') or data.get('symbol_count', 0) <= 0:
        raise AuditError('LLVM_SYMBOLS_MISSING')
    if data.get('status') != 'passed' or data.get('code') != 'OK':
        raise AuditError('INVALID_PROBE_REPORT')


def validated_spirv(spv, reflection, cap):
    spv = Path(spv)
    if not spv.is_file() or spv.is_symlink():
        raise AuditError('SPIRV_MISSING')
    size = spv.stat().st_size
    if size < 20 or size % 4 or size > cap:
        raise AuditError('SPIRV_SIZE_INVALID')
    with spv.open('rb') as handle:
        if handle.read(4) != struct.pack('<I', 0x07230203):
            raise AuditError('SPIRV_MAGIC_INVALID')
    reflection = Path(reflection)
    if not reflection.is_file() or reflection.is_symlink() or reflection.stat().st_size > cap:
        raise AuditError('REFLECTION_MISSING_OR_OVERSIZE')
    try:
        data = strict_json(reflection.read_text())
    except (ValueError, UnicodeError):
        raise AuditError('REFLECTION_JSON_INVALID')
    if not isinstance(data, dict) or not isinstance(data.get('function-infos'), dict) or not data['function-infos']:
        raise AuditError('REFLECTION_FUNCTIONS_MISSING')


def approved_fixtures(root, source):
    policy = strict_json((root / 'config/audit-fixtures.json').read_text())
    if not isinstance(policy, dict) or type(policy.get('schema_version')) is not int or policy.get('schema_version') != 1 or not isinstance(policy.get('approved'), list):
        raise AuditError('INVALID_FIXTURE_POLICY')
    fixtures = []
    for item in policy['approved']:
        if not isinstance(item, dict) or set(item) != {'relative_path', 'sha256', 'license', 'origin', 'evidence_ref'}:
            raise AuditError('INVALID_FIXTURE_APPROVAL')
        if any(not isinstance(value, str) or not value for value in item.values()):
            raise AuditError('INVALID_FIXTURE_APPROVAL')
        path = source / item['relative_path']
        if (path.is_symlink() or not path.is_file() or
                (source / 'test').resolve() not in path.resolve().parents or path.suffix != '.metallib'):
            raise AuditError('FIXTURE_PATH_REFUSED')
        if sha256(path) != item['sha256']:
            raise AuditError('FIXTURE_HASH_MISMATCH')
        fixtures.append((path, item['sha256']))
    return fixtures


def make_candidate(major):
    return {'llvm_major': major, 'status': 'blocked', 'phases': [], 'fixtures': [], 'missing_symbols': []}


def finish_phases(candidate, code):
    present = {item['name'] for item in candidate['phases']}
    for name in PHASES:
        if name not in present:
            candidate['phases'].append(phase(name, 'skipped', code))


def fully_verified(candidate):
    if candidate.get('status') != 'passed' or candidate.get('missing_symbols') != []:
        return False
    phases = candidate.get('phases', [])
    names = {item.get('name') for item in phases}
    if not set(PHASES) <= names or any(item.get('status') != 'passed' for item in phases):
        return False
    fixtures = candidate.get('fixtures', [])
    return bool(fixtures) and all(
        item.get('status') == 'passed' and item.get('code') == 'OK' and
        isinstance(item.get('sha256'), str) and re.fullmatch(r'[a-f0-9]{64}', item['sha256'])
        for item in fixtures)


def baseline(candidates):
    successes = [item['llvm_major'] for item in candidates if fully_verified(item)]
    return min(successes) if successes else None


def audit_candidate(root, source, major, cfg, runner, run_id, operation, tools):
    candidate = make_candidate(major)
    env = candidate_env(major)
    timeout = cfg['probe_timeout_seconds']
    try:
        query_packages(runner, ('llvm-%d' % major, 'llvm-%d-dev' % major), root, env, tools, 'llvm-package-versions')
        llvm = Path('/usr/lib/llvm-%d/bin/llvm-config' % major)
        if shutil.which('llvm-config', path=env['PATH']) != str(llvm) or not llvm.is_file():
            raise AuditError('LLVM_CONFIG_MISSING_OR_SHADOWED', True)
        if not Path(env['LLVM_DIR'], 'LLVMConfig.cmake').is_file():
            raise AuditError('LLVM_CMAKE_CONFIG_MISSING', True)
        version, _ = run_checked(runner, 'llvm-version', [str(llvm), '--version'], root, env, timeout)
        selected_major(version, major)
        tools.append({'name': 'llvm-config-%d' % major, 'version': version, 'status': 'observed'})
        libnames, _ = run_checked(runner, 'llvm-library-name', [str(llvm), '--link-shared', '--libnames'], root, env, timeout)
        libdir, _ = run_checked(runner, 'llvm-library-directory', [str(llvm), '--libdir'], root, env, timeout)
        if len(libnames.split()) != 1:
            raise AuditError('LLVM_SHARED_LIBRARY_AMBIGUOUS')
        expected_library = Path(libdir) / libnames
        if not expected_library.is_file():
            raise AuditError('LLVM_SHARED_LIBRARY_MISSING', True)
        if operation == 'preflight':
            candidate['status'] = 'passed'
            candidate['phases'].append(phase('preflight', 'passed', 'DEPENDENCIES_OBSERVED'))
            finish_phases(candidate, 'PREFLIGHT_ONLY')
            return candidate
        work = root / '.work/build/audit-linux' / run_id / ('llvm-%d' % major)
        work.mkdir(parents=True, exist_ok=False)
        build = work / 'indium'
        compiler = '/usr/bin/clang-%d' % cfg['compiler_major']
        commands = [
            ('configure', ['cmake', '-S', str(source), '-B', str(build), '-G', 'Ninja',
                           '-DENABLE_TESTS=' + ('ON' if cfg['enable_upstream_test_targets'] else 'OFF'),
                           '-DCMAKE_BUILD_TYPE=Release', '-DLLVM_DIR=' + env['LLVM_DIR'],
                           '-DCMAKE_C_COMPILER=' + compiler, '-DCMAKE_CXX_COMPILER=' + compiler.replace('clang-', 'clang++-')], cfg['configure_timeout_seconds']),
            ('build', ['cmake', '--build', str(build), '--parallel', str(cfg['jobs'])], cfg['build_timeout_seconds']),
            ('probe-configure', ['cmake', '-S', str(root / 'tests/llvm-probe'), '-B', str(work / 'probe'), '-G', 'Ninja',
                                 '-DINDIUM_SOURCE=' + str(source), '-DINDIUM_BUILD=' + str(build),
                                 '-DLLVM_DIR=' + env['LLVM_DIR'], '-DCMAKE_CXX_COMPILER=' + compiler.replace('clang-', 'clang++-')], cfg['configure_timeout_seconds']),
            ('probe-build', ['cmake', '--build', str(work / 'probe'), '--parallel', str(cfg['jobs'])], cfg['build_timeout_seconds']),
            ('symbols', [str(work / 'probe/llvm_probe'), str(expected_library)], timeout)]
        for name, argv, deadline in commands:
            item = runner.run(name, argv, root, env, deadline)
            candidate['phases'].append(item)
            if name == 'symbols' and item['stdout_path']:
                try:
                    data = strict_json(runner.text(item))
                    if not isinstance(data, dict):
                        raise AuditError('INVALID_PROBE_REPORT')
                    missing_symbols = data.get('missing_symbols', [])
                    # Keep the failure report schema-valid even for corrupt probe output.
                    if isinstance(missing_symbols, list) and all(isinstance(name, str) for name in missing_symbols):
                        candidate['missing_symbols'] = missing_symbols
                    validate_probe(data, expected_library)
                except (ValueError, TypeError, AuditError) as error:
                    item['status'] = 'failed'
                    item['code'] = error.code if isinstance(error, AuditError) else 'INVALID_PROBE_REPORT'
            if item['status'] != 'passed':
                raise AuditError(item['code'], item['status'] == 'blocked')
        fixtures = approved_fixtures(root, source)
        if not fixtures:
            candidate['status'] = 'build-only'
            candidate['fixtures'].append({'sha256': None, 'status': 'skipped', 'code': 'FIXTURE_PROVENANCE_UNCONFIRMED'})
            finish_phases(candidate, 'FIXTURE_PROVENANCE_UNCONFIRMED')
            return candidate
        for index, (path, digest) in enumerate(fixtures):
            destination = work / ('translation-%d' % index)
            destination.mkdir()
            output = destination / 'shader.spv'
            translated = runner.run('translation', [str(build / 'mtl2spv'), str(path), str(output)], destination, env, cfg['translation_timeout_seconds'])
            candidate['phases'].append(translated)
            if translated['status'] == 'passed':
                try:
                    validated_spirv(output, str(output) + '.json', cfg['max_output_bytes'])
                except AuditError as error:
                    translated['status'], translated['code'] = 'failed', error.code
            if translated['status'] != 'passed':
                candidate['fixtures'].append({'sha256': digest, 'status': 'failed', 'code': translated['code']})
                raise AuditError(translated['code'])
            validated = runner.run('spirv-val', ['spirv-val', '--target-env', 'vulkan1.3', str(output)], destination, env, cfg['translation_timeout_seconds'])
            candidate['phases'].append(validated)
            candidate['fixtures'].append({'sha256': digest, 'status': validated['status'], 'code': validated['code']})
            if validated['status'] != 'passed':
                raise AuditError(validated['code'])
        candidate['status'] = 'passed'
    except (AuditError, OSError, ValueError) as error:
        candidate['status'] = 'blocked' if isinstance(error, AuditError) and error.blocked else 'failed'
        candidate['phases'].append(phase('candidate-error', candidate['status'], error.code if isinstance(error, AuditError) else 'CANDIDATE_IO_OR_JSON_FAILED'))
    finish_phases(candidate, 'PREREQUISITE_NOT_PASSED')
    return candidate


def execute(root, cfg, config_path, output, operation, major=None, host=None, runner=None):
    host = host if host is not None else host_info()
    selected = cfg['llvm_candidates'] if major is None else [major]
    if any(n not in cfg['llvm_candidates'] for n in selected):
        raise AuditError('LLVM_MAJOR_NOT_CONFIGURED')
    run_id = uuid.uuid4().hex
    report = {'schema_version': 1, 'run_id': run_id, 'status': 'blocked', 'operation': operation,
              'host': host, 'config_sha256': sha256(config_path), 'source_revisions': {},
              'tools': [], 'candidates': [], 'baseline_llvm_major': None}
    runner = runner if runner is not None else Runner(output, cfg['max_output_bytes'])
    try:
        if host['os'] != 'Linux' or host['arch'] != cfg['arch']:
            raise AuditError('LINUX_X86_64_REQUIRED', True)
        if host['distribution'] != {'id': cfg['os_id'], 'version_id': cfg['os_version']}:
            raise AuditError('UBUNTU_24_04_REQUIRED', True)
        required = ('git', 'cmake', 'ninja', 'xxd', 'spirv-val', 'dpkg-query',
                    '/usr/bin/clang-18', '/usr/bin/clang++-18')
        missing = [name for name in required if shutil.which(name) is None]
        if missing:
            report['tools'] += [{'name': name, 'version': None, 'status': 'missing'} for name in missing]
            raise AuditError('TOOLS_MISSING', True)
        env = candidate_env(selected[0])
        source, report['source_revisions'] = check_sources(root, runner, env, report['tools'])
        query_packages(runner, COMMON_PACKAGES, root, env, report['tools'])
        for name, argv in [('clang', ['/usr/bin/clang-18', '--version']), ('cmake', ['cmake', '--version']), ('spirv-val', ['spirv-val', '--version'])]:
            value, _ = run_checked(runner, name + '-version', argv, root, env, 30)
            report['tools'].append({'name': name, 'version': value, 'status': 'observed'})
        for candidate in selected:
            report['candidates'].append(audit_candidate(root, source, candidate, cfg, runner, run_id, operation, report['tools']))
        if operation == 'run':
            for candidate in report['candidates']:
                if candidate['status'] == 'passed' and not fully_verified(candidate):
                    candidate['status'] = 'failed'
                    candidate['phases'].append(phase('candidate-contract', 'failed', 'INCOMPLETE_SUCCESS_EVIDENCE'))
            report['baseline_llvm_major'] = baseline(report['candidates'])
        states = [item['status'] for item in report['candidates']]
        report['status'] = 'failed' if 'failed' in states else ('blocked' if any(s != 'passed' for s in states) else 'passed')
    except (AuditError, OSError, ValueError, KeyError, TypeError) as error:
        report['status'] = 'blocked' if isinstance(error, AuditError) and error.blocked else 'failed'
        code = error.code if isinstance(error, AuditError) else 'PREFLIGHT_IO_OR_CONTRACT_FAILED'
        report['candidates'] = [make_candidate(n) for n in selected]
        for candidate in report['candidates']:
            candidate['status'] = report['status']
            candidate['phases'].append(phase('preflight', report['status'], code))
            finish_phases(candidate, code)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('preflight', 'run'))
    parser.add_argument('--config', default='config/audit-linux.json')
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--llvm-major', type=int)
    args = parser.parse_args()
    try:
        cfg = load_config(args.config)
        if args.llvm_major is not None and args.llvm_major not in cfg['llvm_candidates']:
            raise AuditError('LLVM_MAJOR_NOT_CONFIGURED')
        output = new_output(ROOT, args.out_dir)
        report = execute(ROOT, cfg, args.config, output, args.operation, args.llvm_major)
        (output / 'config.json').write_text(json.dumps(cfg, indent=2) + '\n')
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'run_id': report['run_id'], 'status': report['status'], 'report': str(output / 'report.json')}))
        return {'passed': 0, 'blocked': 2, 'failed': 1}[report['status']]
    except (AuditError, OSError, ValueError) as error:
        code = error.code if isinstance(error, AuditError) else 'INPUT_OR_OUTPUT_INVALID'
        print(json.dumps({'status': 'failed', 'code': code}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
