#!/usr/bin/env python3

import sys
import subprocess
import signal
import atexit
import argparse
import tomllib
from pathlib import Path
from pprint import pprint

from .podman_firewall import PodmanFirewall
from .podman_jail import PodmanJail

def podman_remove_containers():
    subprocess.run(
        ["podman", "rm", "-f", PodmanFirewall.NAME, PodmanFirewall.NAME], 
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL
    )

def cleanup():
    print("\nDeleting containers...")
    podman_remove_containers()

atexit.register(cleanup)

def signal_handler(sig, frame):
    print('Got signal', sig)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def parse_config(configfile: Path) -> dict:
    config = {
        "network": {
        },
        "firewall": {
            "enable": True,
            "whitelist": [],
        },
        "jail": {
            "image": "",
            "allow_gpu": False,
            "entrypoint": "",
            "extra_volumes": [],
            "ports": []
        }
    }

    with open(configfile, "rb") as f:
        user_data = tomllib.load(f)
        
        # Safely merge nested dictionaries
        for section in ["network", "jail", "firewall"]:
            if section in user_data:
                config[section].update(user_data[section])

    return config

def parse_cli_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("-w", "--workdir", default='workspace', type=Path, required=True)
    parser.add_argument("-c", "--config", type=Path)

    parser.add_argument("-b", "--bootstrap", action='store_true')

    parser.add_argument("--allow-net", action='store_true')
    parser.add_argument("-s", "--shell", action='store_true')

    args, args_unknown = parser.parse_known_args()

    if args.bootstrap:
        args.allow_net = True
        args.shell = True

    if not args.config:
        args.config = args.workdir.parent / f'{args.workdir.name}.toml'
    if not args.config.exists():
        raise ValueError(f'Config file {args.config} does not exists')

    config = parse_config(args.config)

    if args.allow_net:
        config['firewall']['enable'] = False

    if args.shell:
        config["jail"]["entrypoint"] = "/bin/bash"

    if not config['jail']['image']:
        config['jail']['image'] = f'vibecage-{args.workdir.name}'

    return config, args, args_unknown

def build_image(dockerfile: str, name: str):
    subprocess.run([
        "podman",
        "build",
        "-t", name,
        "-f", dockerfile
    ])

def main():
    config, args, jail_args = parse_cli_args()

    pprint(config)

    workdir = Path(args.workdir).absolute()
    name = workdir.name

    volumes = [
        f"{workdir}:/{name}:Z",
    ]

    if args.bootstrap:
        df = args.workdir.parent / f'{name}.Dockerfile'
        if df.exists():
            build_image(df, f'vibecage-{name}')

        wd = Path(args.workdir)
        wd.mkdir(exist_ok=True)

        bs = args.workdir.parent.absolute() / f'{name}.sh'
        volumes.append(f'{str(bs)}:/{name}/bootstrap.sh:ro,Z,exec')

    volumes += config['jail']['extra_volumes']

    if config['firewall']['enable']:
        firewall = PodmanFirewall(
            whitelist = config['firewall']['whitelist'],
            ports = config['jail']['ports'],
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
        image = config['jail']['image'],
        volumes = volumes,
        allow_gpu = config['jail']['allow_gpu'],
        entrypoint = config['jail']['entrypoint'],
        workdir = f'/{name}',
        **jail_kw
    )

    if config['firewall']['enable']:
        assert firewall
        firewall.set_target(jail.name)
        firewall.start()

    if args.bootstrap:
        jail.start([f'./bootstrap.sh'])
    else:
        jail.start(jail_args)

if __name__ == '__main__':
    main()
