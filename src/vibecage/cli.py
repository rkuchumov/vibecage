#!/usr/bin/env python3

import os
import shutil
import sys
import argparse
import tomllib
import getpass
from string import Template
from pathlib import Path
from pprint import pprint

from .podman_firewall import PodmanFirewall
from .podman_jail import PodmanJail
from .podman import Podman

CAGE_ROOT = Path('.cage')

def parse_config(configfile: Path, no_error: bool) -> dict:
    config = {
        "firewall": {
            "name": "vc-firewall",
            "image": "vc-firewall",
            "enable": True,
            "kill_on_breach": True,
            "whitelist": [],
        },
        "jail": {
            "name": "vc-main",
            "image": "vc-main",
            "allow_gpu": False,
            "mounts": [],
            "envs": [],
            "entrypoint": "/bin/bash",
            "ports": []
        }
    }

    if not configfile.exists():
        if no_error:
            return config
        raise ValueError(f'Config file {configfile} does not exists')

    with open(configfile, "rb") as f:
        user_data = tomllib.load(f)
        
        # Safely merge nested dictionaries
        for section in ["jail", "firewall"]:
            if section in user_data:
                config[section].update(user_data[section])

    return config

def parse_cli_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("-i", "--init", action='store_true')
    parser.add_argument("-b", "--build", action='store_true')
    parser.add_argument("-r", "--run", action='store_true')
    parser.add_argument("-e", "--exec", action='store_true')

    parser.add_argument("--allow-net", action='store_true')

    args, args_unknown = parser.parse_known_args()

    config = parse_config(CAGE_ROOT / 'config.toml', no_error=args.init)

    if args.allow_net:
        config['firewall']['enable'] = False

    return config, args, args_unknown

def do_init(args):
    src_root = Path(__file__).parents[2]
    if src_root == Path.cwd():
        raise ValueError("Already in project src_root")

    tgt_root = CAGE_ROOT
    tgt_root.mkdir(exist_ok=True)

    files = ['Dockerfile']
    for file in files:
        tgt = tgt_root / file
        print('Creating', tgt)
        shutil.copy(src_root / 'workspace' / file, tgt)

    with open(src_root / 'workspace/config.toml', 'r') as fp:
        config_tmpl = Template(fp.read())

    config_path = tgt_root / 'config.toml'
    print('Creating', config_path)
    with open(config_path, 'w') as fp:
        content = config_tmpl.safe_substitute(
            user=os.environ.get('USER', 'ubuntu'),
            workdir=str(Path.cwd())
        )
        fp.write(content)

    sys.exit(0)

def do_build(args, config):
    bargs = {
        'USER_NAME': getpass.getuser()
    }

    Podman.build(
        config['jail']['image'],
        CAGE_ROOT / 'Dockerfile',
        bargs
    )

    sys.exit(0)

def create_volumes(mount_list: list[str]) -> list[str]:
    volumes = []

    root = Path().cwd()

    for mount in mount_list:
        if not mount:
            continue

        parts = mount.split(':')

        if parts[0].startswith('/'):
            path = Path(parts[0])

            if not path.exists():
                if parts[0].endswith('/') and path.is_relative_to(Path.cwd()):
                    path.mkdir(parents=True)
                else:
                    raise ValueError(f'Mount path "{parts[0]}" does not exists and is not a direcotry')

            volumes.append(mount)
        else:
            path = (root / parts[0]).absolute()
            path = str(path)
            options = parts[1] if len(parts) > 1 else 'Z'

            volumes.append(':'.join([path, path, options]))

    return volumes

def do_run(args, config, jail_args):
    pprint(config)

    Podman.setup_signals()

    volumes = create_volumes(config['jail']['mounts'])

    envs = {}
    for name in config['jail']['envs']:
        if name in os.environ:
            envs[name] = os.environ[name]

    if config['firewall']['enable']:
        firewall = PodmanFirewall(
            name = 'vc-workspace-firewall',
            whitelist = config['firewall']['whitelist'],
            ports = config['jail']['ports'],
            logfile = CAGE_ROOT / 'blocked.txt',
        )

        jail_kw = {
            'network_container': firewall.name
        }
    else:
        firewall = None

        jail_kw = {
            'ports': config['jail']['ports']
        }

    jail = PodmanJail(
        name = 'vc-workspace-main',
        image = config['jail']['image'],
        volumes = volumes,
        envs = envs,
        allow_gpu = config['jail']['allow_gpu'],
        entrypoint = config['jail']['entrypoint'],
        workdir = Path.cwd(),
        **jail_kw
    )

    if config['firewall']['enable']:
        assert firewall
        if config['firewall']['kill_on_breach']:
            firewall.set_target(jail.name)
        firewall.start()

    jail.start(jail_args)

    sys.exit(0)

def do_exec(args, config, jail_args):
    if not jail_args:
        cmd = [ config['jail']['entrypoint'] ]
    else:
        cmd = jail_args

    Podman.exec(config['jail']['name'], cmd)
    sys.exit(0)

def main():
    config, args, unknown_args = parse_cli_args()

    if args.init:
        do_init(args)
    if args.build:
        do_build(args, config)
    if args.run:
        do_run(args, config, unknown_args)
    if args.exec:
        do_exec(args, config, unknown_args)

if __name__ == '__main__':
    main()
