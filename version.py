import os, subprocess
__version__ = "1.0.0"
TOOL_NAME = "WB_quantifier"

def get_git_commit():
    try: return subprocess.run(['git','rev-parse','--short','HEAD'], cwd=os.path.dirname(os.path.abspath(__file__)), capture_output=True, text=True, timeout=5).stdout.strip() or 'unknown'
    except Exception: return 'unknown'

def get_version_string():
    return f"{TOOL_NAME} v{__version__} (git {get_git_commit()})"
