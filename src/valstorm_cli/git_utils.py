import subprocess
from pathlib import Path
from typing import Set, Optional

def get_git_root() -> Path:
    """
    Returns the absolute path to the root of the git repository.
    Raises RuntimeError if not inside a git repository.
    """
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return Path(res.stdout.strip())
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Not inside a git repository") from e

def get_git_diff_files(ref: Optional[str] = None) -> Set[Path]:
    """
    Retrieves the absolute paths of all modified/added files.
    If ref is provided, diffs against that reference (commit, branch, tag, etc.).
    If ref is NOT provided, diffs against HEAD (including staged & unstaged modifications)
    and also fetches local untracked files.
    """
    root = get_git_root()
    files = set()
    
    # 1. Validate the reference if provided
    if ref:
        # Check if the ref exists via git rev-parse
        check_rev = subprocess.run(["git", "rev-parse", "--verify", ref], capture_output=True)
        if check_rev.returncode != 0:
            raise ValueError(f"Invalid git reference: {ref}")
            
    # 2. Query git diff for modified, added, renamed, or copied files
    # We use --name-only and --diff-filter to avoid including deleted files (since we want to deploy existing files)
    cmd = ["git", "diff", "--name-only", "--diff-filter=d"]
    if ref:
        cmd.append(ref)
        
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        for line in res.stdout.splitlines():
            line_stripped = line.strip()
            if line_stripped:
                files.add(root / line_stripped)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git diff command failed: {e.stderr}")
        
    # 3. If no reference is provided, also fetch uncommitted/untracked new files using status or diff
    if not ref:
        # Also include staged files if they are new or modified
        try:
            staged_res = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=d"], capture_output=True, text=True, check=True)
            for line in staged_res.stdout.splitlines():
                line_stripped = line.strip()
                if line_stripped:
                    files.add(root / line_stripped)
        except subprocess.CalledProcessError:
            pass

        # Include untracked files
        try:
            status_res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
            for line in status_res.stdout.splitlines():
                if line.startswith("?? "):
                    # Extract the filename part
                    file_rel = line[3:].strip()
                    if file_rel:
                        # Strip surrounding quotes if git printed them (for filenames with spaces)
                        if file_rel.startswith('"') and file_rel.endswith('"'):
                            file_rel = file_rel[1:-1]
                        files.add(root / file_rel)
        except subprocess.CalledProcessError:
            pass
            
    return files
