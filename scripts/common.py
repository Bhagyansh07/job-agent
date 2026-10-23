import os, json, datetime as dt, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_env():
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()


def cfg(name):
    import yaml
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8")) or {}


def today():
    return dt.date.today().isoformat()


def now():
    return dt.datetime.now().strftime("%H:%M")


class FileLock:
    """Tiny cross-process lock file. A lock older than 10 minutes is treated as stale."""

    def __init__(self, path, timeout=30.0):
        self.path, self.timeout = pathlib.Path(path), timeout

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        import time
        deadline = time.time() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > 600:
                        self.path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if time.time() > deadline:
                    raise RuntimeError(f"LOCK_TIMEOUT {self.path}")
                time.sleep(0.2)

    def __exit__(self, *exc):
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


def safe_cell(value):
    """Stop spreadsheet formula injection (values starting with = + - @)."""
    s = "" if value is None else str(value)
    if s[:1] in ("=", "+", "-", "@"):
        try:
            float(s)
            return s
        except ValueError:
            return "'" + s
    return s


def tg_api(method, payload=None, timeout=30):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN missing in .env")
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())
