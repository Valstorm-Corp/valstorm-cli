import json
import sys
import os
from pathlib import Path

def main():
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)
        cwd = input_data.get("cwd", os.getcwd())
        
        # Find project root (where valstorm.json lives)
        root = Path(cwd)
        while root != root.parent:
            if (root / "valstorm.json").exists():
                break
            root = root.parent
        else:
            print(json.dumps({}), flush=True)
            return

        # Documentation is located in valstorm_platform/docs
        platform_docs_dir = root / "valstorm_platform" / "docs"
        if not platform_docs_dir.exists():
            print(json.dumps({}), flush=True)
            return

        # Critical pillar documents to inject for context
        pillar_docs = [
            "admin/Permissions & Role Hierarchy.md",
            "admin/SQL Query Engine.md",
            "admin/ValStorm Field Types & Schema Guide.md",
            "technical/platform/PlatformContext.md",
            "technical/ai/AI_Agent_System.md"
        ]
        
        context_parts = []
        for doc_rel in pillar_docs:
            file_path = platform_docs_dir / doc_rel
            if file_path.exists():
                content = file_path.read_text()
                context_parts.append(f"--- Document: {doc_rel} ---\n{content}")

        if context_parts:
            additional_context = "\n\n".join(context_parts)
            output = {
                "hookSpecificOutput": {
                    "additionalContext": f"The following Valstorm platform documentation has been injected for context:\n\n{additional_context}"
                }
            }
            print(json.dumps(output), flush=True)
        else:
            print(json.dumps({}), flush=True)

    except Exception as e:
        print(f"Error in doc injection hook: {e}", file=sys.stderr)
        print(json.dumps({}), flush=True)

if __name__ == "__main__":
    main()
