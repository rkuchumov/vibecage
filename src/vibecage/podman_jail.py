import subprocess
from .utils import pretty_print_cmd

class PodmanJail():
    NAME = 'vibecage-main'

    def __init__(
        self,
        image: str,
        volumes: list[str] = [],
        ports: list[str] = [],
        workdir: str | None = None,
        network_container: str | None = None,
        entrypoint: str | None = None,
        allow_gpu: bool = False,
    ):
        self._image = image
        self._allow_gpu = allow_gpu
        self._net_container = network_container
        self._ports = ports
        self._volumes = volumes
        self._workdir = workdir
        self._entrypoint = entrypoint

    @property
    def name(self):
        return self.NAME

    def start(self, command: list[str] = []):
        cmd = [
            "podman", "run", "--rm", "-it",
            "--name", self.NAME,
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--userns=keep-id",
            "--group-add", "keep-groups",
            "--shm-size=8g",
        ]

        if self._workdir:
            cmd += ["--workdir", self._workdir]

        for p in self._ports:
            cmd += ['-p', p]

        for v in self._volumes:
            cmd += ['-v', v]

        if self._net_container:
            cmd += [f"--network=container:{self._net_container}"]

        if self._allow_gpu:
            cmd += [
                "--device", "/dev/kfd",
                "--device", "/dev/dri",
            ]

        if self._entrypoint:
            cmd += ["--entrypoint", self._entrypoint]

        cmd += [self._image] + command

        print('Starting Container')
        pretty_print_cmd(cmd)

        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            pass
