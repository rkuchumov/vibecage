import os
import time
import subprocess
import tempfile
import threading
import re
from pathlib import Path
import fnmatch

from .utils import pretty_print_cmd

class PodmanFirewall():
    NAME = 'vibecage-firewall'

    WAIT_DEALAY_SEC = 1

    def __init__(
        self,
        whitelist: list[str],
        ports: list[str],
    ):
        self._ports = ports
        self._kill_target = None

        self._whitelist = set()
        for item in whitelist:
            self._whitelist.add(item.lower().rstrip('.'))

        # Matches: dnsmasq: query[A] api.github.com from 127.0.0.1
        self._re_dns = re.compile(r'query\[[a-zA-Z0-9]+\]\s+([^\s]+)\s+from')
        self._re_ip = re.compile(r'>\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)')

    @property
    def name(self):
        return self.NAME

    def set_target(self, tgt: str):
        self._kill_target = tgt

    def _extract_ip(self, line: str) -> str | None:
        match = self._re_ip.search(line)
        if not match:
            return
        return match.group(1)

    def _extract_domain(self, line: str) -> str | None:
        match = self._re_dns.search(line)
        if not match:
            return

        domain = match.group(1)
        domain = domain.lower().rstrip(".")
        return domain

    def _make_domains_whitelist(self) -> str:
        d = tempfile.mkdtemp(prefix="podrun_oc_")
        p = os.path.join(d, 'domains_whitelist.txt')

        with open(p, 'w') as fp:
            for line in self._whitelist:
                if self._extract_ip(line):
                    continue
                fp.write(line + '\n')

        return p

    def _start_container(self):
        whitelist = self._make_domains_whitelist()

        cmd = [
            "podman", "run", "-d", "--rm",
            "--name", self.name,
            "--cap-add=NET_ADMIN",
            "--cap-add=NET_RAW",
            "--dns=127.0.0.1",
            "-v", f"{whitelist}:/whitelist.txt:ro,Z"
        ]

        for p in self._ports:
            cmd += ['-p', p]

        fw_sciprt = Path(__file__).parent / 'firewall.sh'
        cmd += ['-v', f"{str(fw_sciprt)}:/firewall.sh:ro,Z,exec"]

        cmd += [
            "alpine:latest",
            "sh", "-c", "./firewall.sh"
        ]

        print('Starting Firewall')
        pretty_print_cmd(cmd)

        proc = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            # stderr=subprocess.DEVNULL
        )

        return proc

    def _handle_breach(self, target: str):
        print(f"\nAccess to {target} is not allowed")

        if not self._kill_target:
            return

        print(f"Killing container {self._kill_target}")
        subprocess.run(["podman", "kill", self._kill_target])

    def _address_is_allowed(self, addr: str) -> bool:
        if addr in self._whitelist:
            return True

        for item in self._whitelist:
            if fnmatch.fnmatch(addr, item):
                return True

        return False

    def _monitor_thread(self):
        proc = subprocess.Popen(
            ["podman", "logs", "-f", self.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in proc.stdout:
            ip = self._extract_ip(line)
            if ip and not self._address_is_allowed(ip):
                self._handle_breach(ip)
                break

            domain = self._extract_domain(line)
            if domain and not self._address_is_allowed(domain):
                self._handle_breach(domain)
                break

    def start(self):
        self._podman_proc = self._start_container()
    
        time.sleep(PodmanFirewall.WAIT_DEALAY_SEC)

        mon_thread = threading.Thread(
            target=self._monitor_thread,
            daemon=True
        )

        mon_thread.start()


