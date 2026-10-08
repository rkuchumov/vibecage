#!/usr/bin/env python3

import shutil
import sys
import argparse
import tomllib
from pathlib import Path
from pprint import pprint

from .podman_firewall import PodmanFirewall
from .podman_jail import PodmanJail
from .podman import Podman

def parse_config(configfile: Path, no_error: bool) -> dict:
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

    if not configfile.exists():
        if no_error:
            return config
        raise ValueError(f'Config file {configfile} does not exists')

    with open(configfile, "rb") as f:
        user_data = tomllib.load(f)
        
        # Safely merge nested dictionaries
        for section in ["network", "jail", "firewall"]:
            if section in user_data:
                config[section].update(user_data[section])

    return config

def parse_cli_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("-w", "--workdir", default='workspace', type=Path)
    parser.add_argument("-c", "--config", type=Path)

    parser.add_argument("-b", "--bootstrap", action='store_true')
    parser.add_argument("-i", "--init", action='store_true')
    parser.add_argument("-p", "--port")

    parser.add_argument("--allow-net", action='store_true')
    parser.add_argument("-s", "--shell", action='store_true')

    args, args_unknown = parser.parse_known_args()

    if args.bootstrap:
        args.allow_net = True
        args.shell = True

    if not args.config:
        args.config = args.workdir.parent / f'{args.workdir.name}.toml'

    config = parse_config(args.config, no_error=args.init)

    if args.allow_net:
        config['firewall']['enable'] = False

    if args.shell:
        config["jail"]["entrypoint"] = "/bin/bash"

    if not config['jail']['image']:
        config['jail']['image'] = f'vc-{args.workdir.name}-main'

    if args.port:
        config['jail']['port'] = args.port

    return config, args, args_unknown

def main():
    config, args, jail_args = parse_cli_args()

    workdir = Path(args.workdir).absolute()
    name = workdir.name

    if args.init:
        root = Path(__file__).parents[2]
        if root == Path.cwd():
            raise ValueError("Already in project root")

        exts = ['Dockerfile', 'toml', 'sh']
        for ext in exts:
            tgt = f'{name}.{ext}'
            print('Creating', tgt)
            shutil.copy(root / f'workspace.{ext}', tgt)

        sys.exit(0)

    pprint(config)

    Podman.setup_signals()

    volumes = [
        f"{workdir}:/{name}:Z",
    ]

    if args.bootstrap:
        df = args.workdir.parent / f'{name}.Dockerfile'
        if df.exists():
            Podman.build(df, config['jail']['image'])

        wd = Path(args.workdir)
        wd.mkdir(exist_ok=True)

        bs = args.workdir.parent.absolute() / f'{name}.sh'
        volumes.append(f'{str(bs)}:/{name}/bootstrap.sh:ro,Z,exec')

    volumes += config['jail']['extra_volumes']

    if config['firewall']['enable']:
        firewall = PodmanFirewall(
            workspace = name,
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
        workspace = name,
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
