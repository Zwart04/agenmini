"""Exercise uninstall with isolated paths and fake host commands; never touch the host."""
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'agen-uninstall.sh'


def setup(tmp_path):
    install = tmp_path / 'opt' / 'agenmini'
    install.mkdir(parents=True)
    (install / 'docker-compose.standalone.yml').write_text('services: {}')
    (install / '.env').write_text('SECRET=preserve')
    (install / 'data').mkdir()
    (install / 'data' / 'history').write_text('private')
    sibling = tmp_path / 'other-app'
    sibling.write_text('untouched')
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    log = tmp_path / 'commands'
    for name in ('docker', 'systemctl'):
        cmd = bin_dir / name
        cmd.write_text('#!/bin/sh\nprintf "%s\\n" "' + name + ' $*" >> "$TEST_LOG"\n')
        cmd.chmod(0o755)
    units = tmp_path / 'units'
    units.mkdir()
    for name in ('agenmini-supervisor.service', 'agenmini-supervisor.timer', 'other.service'):
        (units / name).write_text('fixture')
    cli = tmp_path / 'agen'
    cli.write_text('fixture')
    script = tmp_path / 'uninstall.sh'
    script.write_text(SCRIPT.read_text().replace('/opt/agenmini', str(install))
                      .replace('/etc/systemd/system/', str(units) + '/')
                      .replace('/usr/local/bin/agen', str(cli)))
    env = {**os.environ, 'PATH': str(bin_dir) + ':' + os.environ['PATH'], 'TEST_LOG': str(log)}
    return script, env, install, sibling, units, cli, log


def test_full_uninstall_is_scoped_and_stops_recovery_first(tmp_path):
    script, env, install, sibling, units, cli, log = setup(tmp_path)
    subprocess.run(['bash', str(script), '--all', '--yes'], env=env, check=True)
    assert not install.exists()
    assert not cli.exists()
    assert sibling.read_text() == 'untouched'
    assert (units / 'other.service').exists()
    commands = log.read_text().splitlines()
    assert commands[0].startswith('systemctl disable --now agenmini-supervisor.timer')
    assert commands[1].startswith('docker compose --project-name agenmini')
    assert '--volumes' in commands[1]


def test_keep_data_and_dry_run(tmp_path):
    script, env, install, sibling, units, cli, log = setup(tmp_path)
    subprocess.run(['bash', str(script), '--all', '--dry-run'], env=env, check=True)
    assert not log.exists()
    assert cli.exists()
    subprocess.run(['bash', str(script), '--yes'], env=env, check=True)
    assert (install / 'data/history').read_text() == 'private'
    assert (install / '.env').read_text() == 'SECRET=preserve'
    assert '--volumes' not in log.read_text()
    assert sibling.exists()
