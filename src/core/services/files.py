import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Literal
import json

@dataclass
class FileSystemNode:
    name: str
    type: Literal["file", "directory"]
    path: str
    size: Optional[int] = None
    children: Optional[List['FileSystemNode']] = None

class FileSystemVisitor:
    """
    A deterministic visitor for the file system.
    IMPROVED: Implements a "VIP Pass" to capture environment context (The Devil's Advocate Fix).
    """
    
    # Block List: Noise to Ignore
    IGNORED_DIRS = {
        "__pycache__", "node_modules", ".git", ".vscode", ".idea", 
        "dist", "build", "coverage", ".venv", "venv", "env",
        "proc", "sys", "dev", "run", "var", "tmp", "etc", "boot", "srv", "sbin", "bin", "lib", "lib64", "usr", "mnt", "media", "home", "root", "opt",
        "staticfiles", "static", "media", "assets", "templates", 'theme', 'fonts', 'css', 'scss', 'sass', 'img', 'images', 'svg', 'migrations',
        # Additional exclusions to reduce token count
        "vendor", "third_party", "external", "deps", "dependencies",
        ".cache", ".pytest_cache", ".mypy_cache", ".tox", ".nox",
        "htmlcov", "docs", "documentation", "site-packages",
        "eggs", ".eggs", "sdist", "wheels", ".wheel", "pip-wheel-metadata",
        "__pypackages__", "celerybeat-schedule", ".spyderproject", ".spyproject",
    }
    
    IGNORED_FILES = {
        ".DS_Store", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", 
        "Thumbs.db", "desktop.ini", "npm-debug.log",
        # Additional exclusions
        ".coverage", ".env", ".env.local", ".env.production",
        "poetry.lock", "Pipfile.lock", "composer.lock",
        ".gitattributes", ".editorconfig", ".prettierrc",
        "LICENSE", "LICENSE.txt", "LICENSE.md",
    }

    # VIP Filenames: Critical Context files
    VIP_FILENAMES = {
        "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "Makefile", "Justfile", "Procfile", "Vagrantfile",
        "requirements.txt", "Pipfile", "pyproject.toml", "poetry.lock",
        "package.json", "tsconfig.json", 
        "alembic.ini", ".env.example", ".gitignore",
        "README", "LICENSE", "CONTRIBUTING", "CHANGELOG"
    }

    # VIP Extensions: Documentation and Config types
    VIP_EXTENSIONS = {
        ".md", ".markdown",       
        ".txt",                  
        ".yml", ".yaml",          
        ".toml", ".ini", ".cfg",  
        ".json",                  
        ".sh", ".bat",            
        ".rst"                    
    }

    def visit(self, root_path: str, max_depth: int = 4) -> dict:
        path = Path(root_path).resolve()
        if not path.exists():
            raise ValueError(f"Path not found: {root_path}")
            
        node = self._visit_node(path, current_depth=0, max_depth=max_depth)
        return asdict(node) if node else {}

    def _visit_node(self, path: Path, current_depth: int, max_depth: int) -> Optional[FileSystemNode]:
        # 1. The Guard Clauses
        if path.name in self.IGNORED_DIRS or path.name in self.IGNORED_FILES:
            return None
        
        if path.is_file():
            # Skip large files (> 50KB) to reduce token count
            try:
                file_size = path.stat().st_size
                if file_size > 50 * 1024:  # 50KB limit
                    return None
            except:
                return None
            
            # Logic: Allow the file if it is Python, a VIP file, or a VIP extension
            is_python = path.suffix == '.py'
            is_vip_name = path.name in self.VIP_FILENAMES
            is_vip_ext = path.suffix in self.VIP_EXTENSIONS
            
            # If none of the above, ignore it (filter out random files)
            if not (is_python or is_vip_name or is_vip_ext):
                return None

            return FileSystemNode(
                name=path.name,
                type="file",
                path=str(path),
                size=file_size
            )

        # 3. Processing directories
        if path.is_dir():
            if current_depth >= max_depth:
                return FileSystemNode(
                    name=path.name,
                    type="directory",
                    path=str(path),
                    children=[] # Truncated
                )

            children_nodes = []
            try:
                # Sorting entries to ensure consistent output
                entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
                
                for entry in entries:
                    child = self._visit_node(entry, current_depth + 1, max_depth)
                    if child:
                        children_nodes.append(child)
            except PermissionError:
                pass 

            # Improvement: Remove empty directories resulting from ignoring their contents
            # Example: The css folder will become empty and will be removed from the tree to keep it clean
            if not children_nodes and current_depth != 0:
                return None

            return FileSystemNode(
                name=path.name,
                type="directory",
                path=str(path),
                children=children_nodes
            )
            
        return None

# ---------------------------------------------------------
# The Formatter (Visualizer)
# ---------------------------------------------------------
class TreeFormatter:
    def format(self, node_dict: dict) -> str:
        lines = []
        self._render(node_dict, lines, "", is_last=True)
        return "\n".join(lines)

    def _render(self, node: dict, lines: list, prefix: str, is_last: bool):
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{node['name']}")
        
        prefix += "    " if is_last else "│   "
        
        children = node.get("children", []) or []
        count = len(children)
        
        for i, child in enumerate(children):
            self._render(child, lines, prefix, i == count - 1)

if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent.parent 
    
    # project_root = Path(".")

    print(f"Scanning Root: {project_root.resolve()}")
    
    visitor = FileSystemVisitor()
    tree_dict = visitor.visit(str(project_root), max_depth=5)
    
    formatter = TreeFormatter()
    print("\n--- Project Visual Tree ---")
    print(formatter.format(tree_dict))
    
    output_file = Path("project_tree.txt")
    output_json = Path("project_tree.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(formatter.format(tree_dict))
    with open(output_json, "w", encoding="utf-8") as f:
        f.write(json.dumps(tree_dict, indent=2))
        
    print(f"\n✅ Project tree saved to {output_file.resolve()}")