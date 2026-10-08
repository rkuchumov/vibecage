import sys
import signal
import subprocess
import atexit
import abc
from .utils import pretty_print_cmd

class Podman(abc.ABC):
    ACTIVE = []

    def __init__(self, name: str):
        self._name = name
        pass

    @property
    def name(self) -> str:
        return self._name

    @staticmethod
    def cleanup():
        if not Podman.ACTIVE:
            return

        cmd = ["podman", "rm", "-f"]

        for pod in Podman.ACTIVE:
            cmd.append(pod.name)
            pod.stop()

        subprocess.run(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )

    @staticmethod
    def on_signal(sig, frame):
        print('Got Signal', sig)
        sys.exit(0)

    @staticmethod
    def setup_signals():
        atexit.register(Podman.cleanup)
        signal.signal(signal.SIGINT, Podman.on_signal)
        signal.signal(signal.SIGTERM, Podman.on_signal)

    @staticmethod
    def build(dockerfile: str, name: str):
        subprocess.run([
            "podman",
            "build",
            "-t", name,
            "-f", dockerfile
        ])
    
    def start_container(
        self,
        cmd: list[str],
        no_stdout: bool = False,
        no_stderr: bool = False,
    ):
        print(f'Starting {self.name}')
        pretty_print_cmd(cmd)

        kw = {}
        if no_stdout:
            kw['stdout'] = subprocess.DEVNULL 
        if no_stderr:
            kw['stderr'] = subprocess.DEVNULL 

        try:
            proc = subprocess.run(
                cmd,
                check=True,
                **kw
            )

            Podman.ACTIVE.append(self)

            return proc
        except KeyboardInterrupt:
            pass

    def tail_logs(self):
        cmd = ["podman", "logs", "--since=0s", "-f", self.name]
        print(f'Starting log tail for {self.name}')
        pretty_print_cmd(cmd)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        return proc

    @abc.abstractmethod
    def start(self, args: list[str] = []):
        pass

    @abc.abstractmethod
    def stop(self):
        pass
