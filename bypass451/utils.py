import os
import re
import sys
from typing import List, Sequence

if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        h_out = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(h_out, ctypes.byref(mode)):
            kernel32.SetConsoleMode(h_out, mode.value | 0x0004)
    except Exception:
        pass

NO_COLOR = bool(os.environ.get("NO_COLOR") or not sys.stdout.isatty())
ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*m")

class Colors:
    RESET = "" if NO_COLOR else "\033[0m"
    BOLD = "" if NO_COLOR else "\033[1m"
    DIM = "" if NO_COLOR else "\033[2m"
    RED = "" if NO_COLOR else "\033[31m"
    GREEN = "" if NO_COLOR else "\033[32m"
    YELLOW = "" if NO_COLOR else "\033[33m"
    BLUE = "" if NO_COLOR else "\033[34m"
    MAGENTA = "" if NO_COLOR else "\033[35m"
    CYAN = "" if NO_COLOR else "\033[36m"
    WHITE = "" if NO_COLOR else "\033[37m"

def colorize(text: str, color: str) -> str:
    return f"{color}{text}{Colors.RESET}"

def success(text: str) -> str:
    return colorize(f"[+] {text}", Colors.GREEN)

def info(text: str) -> str:
    return colorize(f"[*] {text}", Colors.CYAN)

def warn(text: str) -> str:
    return colorize(f"[!] {text}", Colors.YELLOW)

def error(text: str) -> str:
    return colorize(f"[-] {text}", Colors.RED)

def mask_token(token: str) -> str:
    if not token or len(token) <= 8:
        return "****"
    return f"{token[:4]}...{token[-4:]}"

DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$"
)

def normalize_domain(input_str: str) -> str:
    d = input_str.strip()
    if d.startswith("https://"):
        d = d[8:]
    elif d.startswith("http://"):
        d = d[7:]
    
    slash_idx = d.find("/")
    if slash_idx != -1:
        d = d[:slash_idx]
        
    colon_idx = d.find(":")
    if colon_idx != -1:
        d = d[:colon_idx]
        
    return d.lower().strip()

def is_valid_domain(domain: str) -> bool:
    if not domain or len(domain) > 253:
        return False
    if domain.startswith(".") or domain.endswith("."):
        return False
    return bool(DOMAIN_REGEX.match(domain))

def visible_length(text: str) -> int:
    return len(ANSI_REGEX.sub("", str(text)))

def print_table(headers: Sequence[str], rows: Sequence[Sequence[str]], min_col_width: int = 10) -> None:
    if not rows and not headers:
        return
        
    col_widths = [visible_length(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            v_len = visible_length(val)
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], v_len)
            else:
                col_widths.append(max(min_col_width, v_len))
                
    header_line = "  ".join(
        h + (" " * (col_widths[i] - visible_length(h)))
        for i, h in enumerate(headers)
    )
    sep_line = "  ".join("-" * col_widths[i] for i in range(len(headers)))
    
    print(colorize(header_line, Colors.BOLD))
    print(colorize(sep_line, Colors.DIM))
    for row in rows:
        line_parts = []
        for i, val in enumerate(row):
            val_str = str(val)
            padding = col_widths[i] - visible_length(val_str)
            line_parts.append(val_str + (" " * max(0, padding)))
        print("  ".join(line_parts))
