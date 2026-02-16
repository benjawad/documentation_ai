def find_entry_points(path: str) -> dict:
    """
    Identify main application entry points.
    
    Args:
        path: Project root path
        
    Returns:
        {
            "success": bool,
            "project_type": str,  # "django", "fastapi", "flask", "generic"
            "entry_points": [
                {"type": str, "path": str, "description": str}
            ]
        }
    """
    import os
    from pathlib import Path
    
    root = Path(path).resolve()
    entry_points = []
    project_type = "generic"
    
    # Common entry point patterns
    patterns = {
        "django": [
            ("manage.py", "Django management script"),
            ("**/settings.py", "Django settings"),
            ("**/urls.py", "URL routing"),
            ("**/wsgi.py", "WSGI application"),
            ("**/asgi.py", "ASGI application"),
        ],
        "fastapi": [
            ("main.py", "FastAPI application"),
            ("app/main.py", "FastAPI application"),
            ("**/app.py", "Application factory"),
        ],
        "flask": [
            ("app.py", "Flask application"),
            ("run.py", "Flask runner"),
            ("**/wsgi.py", "WSGI application"),
        ],
        "celery": [
            ("**/celery.py", "Celery configuration"),
        ],
    }
    
    # Detect project type
    if (root / "manage.py").exists():
        project_type = "django"
    elif any((root / "main.py").exists(), (root / "app" / "main.py").exists()):
        project_type = "fastapi"
    elif (root / "app.py").exists():
        project_type = "flask"
    
    # Find entry points
    for pattern_type, pattern_list in patterns.items():
        for pattern, description in pattern_list:
            if "*" in pattern:
                # Glob pattern
                matches = list(root.glob(pattern))
            else:
                # Direct path
                matches = [root / pattern] if (root / pattern).exists() else []
            
            for match in matches:
                if match.is_file():
                    entry_points.append({
                        "type": pattern_type,
                        "path": str(match.relative_to(root)),
                        "description": description
                    })
    
    # Add __main__.py if exists
    if (root / "__main__.py").exists():
        entry_points.append({
            "type": "python_main",
            "path": "__main__.py",
            "description": "Python module entry point"
        })
    
    return {
        "success": True,
        "project_type": project_type,
        "entry_points": entry_points,
        "total_entry_points": len(entry_points)
    }


def list_modules(
    path: str,
    pattern: str = "**/*.py",
    exclude_tests: bool = True,
    exclude_private: bool = True,
    include_stats: bool = True
) -> dict:
    """
    List Python modules with optional filtering and basic stats.
    
    Args:
        path: Directory path
        pattern: Glob pattern (default: **/*.py for recursive)
        exclude_tests: Skip test files
        exclude_private: Skip __pycache__, __init__.py
        include_stats: Calculate LOC and class count (fast regex)
        
    Returns:
        {
            "success": bool,
            "path": str,
            "total_modules": int,
            "modules": [
                {
                    "path": str,
                    "name": str,
                    "size": int,
                    "lines": int,  # if include_stats
                    "classes": int,  # if include_stats
                    "functions": int  # if include_stats
                }
            ]
        }
    """
    import re
    from pathlib import Path
    
    root = Path(path).resolve()
    modules = []
    
    # Find all Python files
    py_files = root.glob(pattern)
    
    for py_file in py_files:
        # Apply filters
        if exclude_tests and ("test_" in py_file.name or "/tests/" in str(py_file)):
            continue
        if exclude_private and ("__pycache__" in str(py_file)):
            continue
        
        module_info = {
            "path": str(py_file.relative_to(root)),
            "name": py_file.name,
            "size": py_file.stat().st_size
        }
        
        # Quick stats without full AST parsing
        if include_stats:
            try:
                content = py_file.read_text(encoding='utf-8')
                
                # Fast regex counts (not perfect but fast)
                module_info["lines"] = content.count('\n')
                module_info["classes"] = len(re.findall(r'^class\s+\w+', content, re.MULTILINE))
                module_info["functions"] = len(re.findall(r'^def\s+\w+', content, re.MULTILINE))
                
            except Exception:
                module_info["lines"] = 0
                module_info["classes"] = 0
                module_info["functions"] = 0
        
        modules.append(module_info)
    
    return {
        "success": True,
        "path": str(root),
        "total_modules": len(modules),
        "modules": sorted(modules, key=lambda x: x["path"])
    }


def get_file_metadata(file_path: str, include_imports: bool = True) -> dict:
    """
    Get file metadata without full AST parsing.
    
    Args:
        file_path: Path to Python file
        include_imports: Extract import statements (fast regex)
        
    Returns:
        {
            "success": bool,
            "path": str,
            "name": str,
            "size": int,
            "lines": int,
            "modified": str,  # ISO format
            "hash": str,  # SHA256 of content
            "imports": [str],  # if include_imports
            "error": str | None
        }
    """
    import hashlib
    import re
    from datetime import datetime
    from pathlib import Path
    
    try:
        file_path = Path(file_path).resolve()
        
        if not file_path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        # Basic file stats
        stat = file_path.stat()
        content = file_path.read_text(encoding='utf-8')
        
        result = {
            "success": True,
            "path": str(file_path),
            "name": file_path.name,
            "size": stat.st_size,
            "lines": content.count('\n'),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "hash": hashlib.sha256(content.encode()).hexdigest()[:16]
        }
        
        # Fast import extraction (regex, not AST)
        if include_imports:
            import_patterns = [
                r'^import\s+([\w\.]+)',
                r'^from\s+([\w\.]+)\s+import',
            ]
            imports = set()
            for pattern in import_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                imports.update(matches)
            
            result["imports"] = sorted(list(imports))
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }