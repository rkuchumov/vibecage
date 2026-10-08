from .podman import Podman

class PodmanJail(Podman):
    def __init__(
        self,
        workspace: str,
        image: str,
        volumes: list[str] = [],
        ports: list[str] = [],
        workdir: str | None = None,
        network_container: str | None = None,
        entrypoint: str | None = None,
        allow_gpu: bool = False,
    ):
        super().__init__(f'vc-{workspace}-main')

        self._image = image
        self._allow_gpu = allow_gpu
        self._net_container = network_container
        self._ports = ports
        self._volumes = volumes
        self._workdir = workdir
        self._entrypoint = entrypoint

    def _make_command(self, command: list[str] = []):
        cmd = [
            "podman", "run", "--rm", "-it",
            "--name", self.name,
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

        # cmd += ['--log-level=debug']

        cmd += [self._image] + command

        return cmd

    def start(self, args: list[str] = []):
        cmd = self._make_command(args)
        self.start_container(cmd)

    def stop(self):
        pass
