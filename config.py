"""Central configuration for chat-to-pdf."""

import os
import sys
import shutil
from pathlib import Path


# ---------------------------------------------------------------------------
# 0. Purge proxy environment variables
# ---------------------------------------------------------------------------

if os.environ.get("CHATPDF_KEEP_PROXY") != "1":
    _PROXY_KEYS = (
        "http_proxy", "https_proxy", "ftp_proxy", "all_proxy", "no_proxy",
        "HTTP_PROXY", "HTTPS_PROXY", "FTP_PROXY", "ALL_PROXY", "NO_PROXY",
    )
    for _k in _PROXY_KEYS:
        os.environ.pop(_k, None)


# ---------------------------------------------------------------------------
# 1. Load .env
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
_env_path = BASE_DIR / ".env"

if _env_path.exists():
    try:
        for line in _env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())
    except (PermissionError, OSError) as e:
        print(f"⚠️  Could not read .env ({e}). Continuing without it.")


# ---------------------------------------------------------------------------
# 2. Resolve paths
# ---------------------------------------------------------------------------

def _resolve(env_var: str, default: Path) -> Path:
    raw = os.environ.get(env_var)
    return Path(raw).expanduser().resolve() if raw else default.resolve()


_data_dir      = _resolve("CHATPDF_DATA_DIR",     BASE_DIR)
SESSIONS_DIR   = _resolve("CHATPDF_SESSIONS_DIR", _data_dir / "sessions")
PROFILES_DIR   = _resolve("CHATPDF_PROFILES_DIR", _data_dir / "profiles")
LOGS_DIR       = _resolve("CHATPDF_LOGS_DIR",     _data_dir / "logs")
TEMPLATE_PROFILE = PROFILES_DIR / "trusted_template"


# ---------------------------------------------------------------------------
# 3. Directory checks
# ---------------------------------------------------------------------------

def _current_username() -> str:
    try:
        import pwd
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        return os.environ.get("USER") or os.environ.get("LOGNAME") or "unknown"


def _ensure_writable(path: Path, label: str) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        parent = path.parent
        me = _current_username()
        raise RuntimeError(
            f"\n❌ Cannot create {label} directory:\n"
            f"   Path:   {path}\n"
            f"   Parent: {parent}\n"
            f"   User:   {me}\n"
            f"\n   Fix with:\n"
            f"     sudo mkdir -p {path}\n"
            f"     sudo chown -R {me}:{me} {path}\n"
        )
    except OSError as e:
        raise RuntimeError(
            f"\n❌ Failed to create {label} directory:\n"
            f"   Path: {path}\n"
            f"   Error: {e}\n"
        )

    if not os.access(path, os.W_OK | os.X_OK):
        try:
            stat = path.stat()
            import pwd
            owner = pwd.getpwuid(stat.st_uid).pw_name
        except Exception:
            owner = "unknown"
        me = _current_username()
        raise RuntimeError(
            f"\n❌ {label} directory not writable:\n"
            f"   Path:  {path}\n"
            f"   Owner: {owner}\n"
            f"   User:  {me}\n"
            f"\n   Fix:\n"
            f"     sudo chown -R {me}:{me} {path.parent}\n"
            f"     rm -rf {path}/*\n"
        )


if os.environ.get("CHATPDF_SKIP_CHECKS") != "1":
    for _p, _label in (
        (SESSIONS_DIR, "sessions"),
        (PROFILES_DIR, "profiles"),
        (LOGS_DIR,     "logs"),
    ):
        _ensure_writable(_p, _label)


def config_summary() -> str:
    lines = [
        "── chat-to-pdf configuration ────────────────────────",
        f"  sessions : {SESSIONS_DIR}",
        f"  profiles : {PROFILES_DIR}",
        f"  logs     : {LOGS_DIR}",
        f"  user     : {_current_username()} (uid={os.getuid()})",
        f"  python   : {sys.version.split()[0]}",
        f"  Xvfb     : {XVFB_BIN}",
        f"  x11vnc   : {X11VNC_BIN}",
        f"  wsockify : {WEBSOCKIFY_BIN}",
        f"  mode     : {'FORCED XVFB' if os.environ.get('CHATPDF_FORCE_XVFB') == '1' else 'auto'}",
        "─────────────────────────────────────────────────────",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. Flask
# ---------------------------------------------------------------------------

SECRET_KEY   = os.environ.get("SECRET_KEY",   "dev-secret-change-me")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "changeme")

if SECRET_KEY == "dev-secret-change-me" or APP_PASSWORD == "changeme":
    print("⚠️  Using default SECRET_KEY / APP_PASSWORD. Set them in .env (VPS).")


# ---------------------------------------------------------------------------
# 5. Session / browser settings
# ---------------------------------------------------------------------------

XVFB_DISPLAY_START    = int(os.environ.get("CHATPDF_XVFB_START",    99))
XVFB_DISPLAY_END      = int(os.environ.get("CHATPDF_XVFB_END",     130))
VNC_PORT_START        = int(os.environ.get("CHATPDF_VNC_START",   5900))
VNC_PORT_END          = int(os.environ.get("CHATPDF_VNC_END",     5930))
WEBSOCKIFY_PORT_START = int(os.environ.get("CHATPDF_WS_START",    6080))
WEBSOCKIFY_PORT_END   = int(os.environ.get("CHATPDF_WS_END",      6110))

NOVNC_WEB_ROOT = os.environ.get("CHATPDF_NOVNC_ROOT", "/usr/share/novnc")

MAX_CONCURRENT_SESSIONS = int(os.environ.get("CHATPDF_MAX_SESSIONS", "3"))
SESSION_TIMEOUT_SECONDS = int(os.environ.get("CHATPDF_SESSION_TIMEOUT", str(30 * 60)))
CAPTCHA_WAIT_SECONDS    = int(os.environ.get("CHATPDF_CAPTCHA_TIMEOUT", str(5 * 60)))


# ---------------------------------------------------------------------------
# 6. Domain allowlist — explicit hosts + pattern matching
# ---------------------------------------------------------------------------
# The tool accepts:
#   1. Any host in ALLOWED_HOSTS (exact or subdomain match).
#   2. Any host containing one of AI_HOST_KEYWORDS.
#
# This means share.google/aimode/..., perplexity.ai/..., grok.com/share/...,
# meta.ai/s/..., copilot.microsoft.com/..., and qwen.aliyun.com/share/...
# all work out of the box, along with hundreds of smaller AI platforms.

_default_hosts = (
    # Core platforms
    "chatgpt.com",
    "chat.openai.com",
    "claude.ai",
    "gemini.google.com",
    "share.gemini.google",
    "g.co",
    "chat.deepseek.com",
    "deepseek.com",
    # New platforms
    "share.google",           # Google AI Mode
    "perplexity.ai",
    "www.perplexity.ai",
    "grok.com",
    "x.com",                  # X Grok share links
    "grok.x.ai",
    "meta.ai",
    "www.meta.ai",
    "copilot.microsoft.com",
    "github.com",             # GitHub Copilot share
    "qwen.aliyun.com",
    "chat.qwen.ai",
    "tongyi.aliyun.com",
    "qianwen.com",
    "mistral.ai",
    "chat.mistral.ai",
    "poe.com",
    "you.com",
    "phind.com",
    "kimi.moonshot.cn",
    "doubao.com",
    "character.ai",
)

# Any hostname containing one of these substrings is accepted.
AI_HOST_KEYWORDS = (
    "ai",           # covers meta.ai, grok.x.ai, chat.qwen.ai, etc.
    "chat",         # covers chatgpt, chat.deepseek, chat.mistral, etc.
    "chatbot",
    "grok",
    "copilot",
    "qwen",
    "perplexity",
    "gemini",
    "deepseek",
    "claude",
    "openai",
    "anthropic",
    "llm",
    "gpt",
    "mistral",
    "poe",
    "phind",
)

_override = os.environ.get("CHATPDF_ALLOWED_HOSTS")
ALLOWED_HOSTS = (
    tuple(h.strip() for h in _override.split(",") if h.strip())
    if _override
    else _default_hosts
)


def is_host_allowed(url_or_host: str) -> bool:
    """
    Return True if the given URL or hostname is allowed.

    Accepts:
      • Exact matches against ALLOWED_HOSTS
      • Subdomain matches against ALLOWED_HOSTS
      • Any host containing an AI_HOST_KEYWORDS substring
    """
    from urllib.parse import urlparse
    try:
        # Accept both full URLs and bare hostnames
        if "://" in url_or_host:
            host = (urlparse(url_or_host).hostname or "").lower()
        else:
            host = url_or_host.lower()
    except Exception:
        return False

    if not host:
        return False

    # 1. Exact or subdomain match against the explicit allowlist
    for d in ALLOWED_HOSTS:
        if host == d or host.endswith("." + d):
            return True

    # 2. Pattern match: any host containing an AI keyword
    for kw in AI_HOST_KEYWORDS:
        if kw in host:
            return True

    return False


# ---------------------------------------------------------------------------
# 7. Chrome launch arguments
# ---------------------------------------------------------------------------

CHROME_ARGS_REAL_DISPLAY = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-http2",
    "--disable-quic",
]

CHROME_ARGS_XVFB = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-infobars",
    "--disable-blink-features=AutomationControlled",
    "--no-proxy-server",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-http2",
    "--disable-quic",
]

CHROME_ARGS = CHROME_ARGS_XVFB


# ---------------------------------------------------------------------------
# 8. Binary resolution
# ---------------------------------------------------------------------------

def _find_binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for d in ("/usr/bin", "/usr/local/bin", "/bin", "/sbin",
              "/usr/sbin", "/opt/local/bin"):
        candidate = Path(d) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise RuntimeError(
        f"\n❌ Required binary not found: {name}\n"
        f"   Install: sudo apt install -y xvfb x11vnc websockify novnc\n"
    )


if os.environ.get("CHATPDF_SKIP_CHECKS") != "1":
    XVFB_BIN       = _find_binary("Xvfb")
    X11VNC_BIN     = _find_binary("x11vnc")
    WEBSOCKIFY_BIN = _find_binary("websockify")
else:
    XVFB_BIN       = "Xvfb"
    X11VNC_BIN     = "x11vnc"
    WEBSOCKIFY_BIN = "websockify"
