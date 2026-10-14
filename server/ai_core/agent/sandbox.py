"""
Runs model-written Python in a separate process with limits.

With bubblewrap (bwrap) installed, the code sees only a read-only Python install
and its own working directory, with no network: not the server's files or .env.
Without it, it falls back to a plain subprocess with the same time, memory and
file-size limits and sockets disabled, but it can still read files the server
user can read. Use bwrap (or a container) wherever untrusted input is possible.

The working directory holds read-only copies of the chat's documents under their
file names, so code can open them directly (pd.read_csv("results.csv")).
"""
import ast
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

MAX_OUTPUT_CHARS = 8000
MAX_FILE_BYTES = 50 * 1024 * 1024

# Used only without bwrap: a best-effort network block in front of the code.
NO_NETWORK_PRELUDE = '''
import socket as _socket
def _no_network(*args, **kwargs):
    raise OSError("Network access is disabled in the sandbox")
_socket.socket.connect = _socket.socket.connect_ex = _no_network
_socket.create_connection = _socket.getaddrinfo = _no_network
del _socket, _no_network
'''


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool = False


def sandbox_mode() -> str:
    """"bwrap", "subprocess" or "off" (no code execution)."""
    mode = settings.CODE_SANDBOX
    if mode == "auto":
        return "bwrap" if shutil.which("bwrap") else "subprocess"
    return mode


def _limits(timeout: int, memory_mb: int):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (timeout + 1, timeout + 1))
        resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    return apply


def _command(mode: str, workdir: Path) -> list[str]:
    # Normalise "server/../.venv/bin/python": the sandbox only contains the venv itself.
    python = os.path.normpath(os.path.abspath(sys.executable))
    if mode == "subprocess":
        return [python, "-I", "main.py"]
    venv = str(Path(sys.prefix).resolve())
    return [
        "bwrap", "--die-with-parent", "--unshare-all", "--new-session",
        "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
        "--ro-bind", venv, venv,
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--bind", str(workdir), "/work", "--chdir", "/work",
        "--clearenv", "--setenv", "HOME", "/work", "--setenv", "PATH", "/usr/bin",
        "--setenv", "OPENBLAS_NUM_THREADS", "1", "--setenv", "OMP_NUM_THREADS", "1", "--setenv", "MPLBACKEND", "Agg",
        python, "-I", "main.py",
    ]


def show_last_expression(code: str) -> str:
    """Like a notebook: a bare expression on the last line has its value printed."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code  # let Python report it
    if not tree.body or not isinstance(tree.body[-1], ast.Expr):
        return code
    last = tree.body[-1].value
    if isinstance(last, ast.Call) and isinstance(last.func, ast.Name) and last.func.id == "print":
        return code
    show = ast.parse("_value = None\nif _value is not None:\n    print(_value)").body
    show[0].value = last
    tree.body[-1:] = show
    return ast.unparse(ast.fix_missing_locations(tree))


def _cut(text: str) -> str:
    return text if len(text) <= MAX_OUTPUT_CHARS else text[:MAX_OUTPUT_CHARS] + "\n[... output cut]"


def run_python(code: str, files: list[tuple[str, str]], timeout: int | None = None, memory_mb: int | None = None) -> SandboxResult:
    """Runs `code` with read-only copies of `files` ([(name, path)]) in its working directory."""
    mode = sandbox_mode()
    if mode == "off":
        return SandboxResult("", "Code execution is turned off on this server.", None)
    timeout = timeout or settings.CODE_TIMEOUT
    memory_mb = memory_mb or settings.CODE_MEMORY_MB

    with tempfile.TemporaryDirectory(prefix="deepquery-sandbox-") as tmp:
        workdir = Path(tmp)
        for name, path in files:
            target = workdir / Path(name).name  # never let a name escape the directory
            shutil.copyfile(path, target)
            target.chmod(0o444)
        prelude = NO_NETWORK_PRELUDE if mode == "subprocess" else ""
        (workdir / "main.py").write_text(prelude + show_last_expression(code), encoding="utf-8")

        env = {"HOME": tmp, "PATH": "/usr/bin:/bin", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MPLBACKEND": "Agg"}
        process = subprocess.Popen(
            _command(mode, workdir), cwd=tmp, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=_limits(timeout, memory_mb), start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            timed_out = True

    return SandboxResult(
        _cut(stdout.decode("utf-8", errors="replace")),
        _cut(stderr.decode("utf-8", errors="replace")),
        process.returncode,
        timed_out,
    )
