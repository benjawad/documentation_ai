import ast
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

from architecture_service import ArchitectureVisitor
from relationship_service import RelationshipExtractor, EnhancedProjectAnalyzer

logger = logging.getLogger(__name__)

# Configuration
MAX_FILE_SIZE = 100_000  # 100KB
SUPPORTED_EXTENSIONS = {'.py'}


@dataclass
class AnalysisError:
    """Error during analysis"""
    file_path: str
    error_type: str
    message: str


def analyze_file(file_path: str) -> dict:
    """
    Analyze a single Python file without full project scan.
    
    **Use when:**
    - User asks about ONE specific file
    - Debugging a single module  
    - Need quick file-level understanding
    - Incremental analysis after file changes
    
    **Token efficiency:** ~300 tokens vs 30,000 for full project
    
    Args:
        file_path: Absolute or relative path to .py file
        
    Returns:
        {
            "success": bool,
            "file_path": str,
            "file_name": str,
            "size": int,
            "classes": [
                {
                    "name": str,
                    "type": "class",
                    "bases": [str],
                    "methods": [{"name": str, "args": [str], "returns": str, "description": str}],
                    "attributes": [{"name": str, "type": str}],
                    "description": str
                }
            ],
            "global_functions": [
                {"name": str, "args": [str], "returns": str, "description": str}
            ],
            "imports": [str],
            "total_classes": int,
            "total_methods": int,
            "total_functions": int,
            "error": str | None
        }
    
    Example:
        >>> analyze_file("/app/core/services/chat_service.py")
        {
            "success": True,
            "file_name": "chat_service.py",
            "classes": [
                {
                    "name": "ChatbotService",
                    "bases": [],
                    "methods": ["__init__", "chat", "get_history"],
                    ...
                }
            ],
            "total_classes": 1,
            "total_methods": 8
        }
    """
    
    try:
        # Validate path
        path = Path(file_path)
        
        if not path.exists():
            return {
                "success": False,
                "file_path": str(file_path),
                "error": f"File not found: {file_path}"
            }
        
        if not path.is_file():
            return {
                "success": False,
                "file_path": str(file_path),
                "error": f"Path is not a file: {file_path}"
            }
        
        if path.suffix not in SUPPORTED_EXTENSIONS:
            return {
                "success": False,
                "file_path": str(file_path),
                "error": f"Unsupported file type: {path.suffix}. Only .py files supported."
            }
        
        # Check file size
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return {
                "success": False,
                "file_path": str(file_path),
                "file_name": path.name,
                "size": file_size,
                "error": f"File too large: {file_size} bytes (max {MAX_FILE_SIZE})"
            }
        
        # Skip symlinks
        if path.is_symlink():
            return {
                "success": False,
                "file_path": str(file_path),
                "error": "Symlinks not supported for security"
            }
        
        # Read file content
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Fallback to latin-1
            try:
                with open(path, 'r', encoding='latin-1') as f:
                    content = f.read()
            except Exception as e:
                return {
                    "success": False,
                    "file_path": str(file_path),
                    "error": f"Encoding error: {str(e)}"
                }
        
        # Parse AST
        try:
            tree = ast.parse(content, filename=str(path))
        except SyntaxError as e:
            return {
                "success": False,
                "file_path": str(file_path),
                "file_name": path.name,
                "size": file_size,
                "error": f"Syntax error at line {e.lineno}: {e.msg}"
            }
        
        # Visit AST
        visitor = ArchitectureVisitor()
        visitor.visit(tree)
        
        # Extract imports (bonus feature)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}" if module else alias.name)
        
        # Calculate statistics
        total_methods = sum(len(cls.get('methods', [])) for cls in visitor.structure)
        
        return {
            "success": True,
            "file_path": str(path.absolute()),
            "file_name": path.name,
            "size": file_size,
            "classes": visitor.structure,
            "global_functions": visitor.global_functions,
            "imports": sorted(set(imports)),  # Deduplicate and sort
            "total_classes": len(visitor.structure),
            "total_methods": total_methods,
            "total_functions": len(visitor.global_functions),
            "error": None
        }
        
    except Exception as e:
        logger.error(f"Unexpected error analyzing {file_path}: {e}", exc_info=True)
        return {
            "success": False,
            "file_path": str(file_path),
            "error": f"Unexpected error: {str(e)}"
        }


def get_core_classes(
    path: str,
    min_connections: int = 2,
    include_metrics: bool = True
) -> dict:
    """
    Identify most connected classes (architectural hotspots).
    
    **Use when:**
    - "What are the main classes?"
    - "Show me the core architecture"
    - Planning refactoring
    - Understanding system entry points
    
    **Token efficiency:** ~100 tokens vs 30,000 for manual analysis
    
    Args:
        path: Project root path
        min_connections: Minimum total relationships (inherits + uses)
        include_metrics: Include detailed connection metrics
        
    Returns:
        {
            "success": bool,
            "total_classes": int,
            "core_classes": [
                {
                    "name": str,
                    "module": str,
                    "total_connections": int,
                    "inherits_count": int,
                    "uses_count": int,
                    "used_by_count": int,  # (if include_metrics)
                    "description": str
                }
            ],
            "threshold": int,
            "error": str | None
        }
    
    Example:
        >>> get_core_classes("/app", min_connections=3)
        {
            "success": True,
            "total_classes": 47,
            "core_classes": [
                {
                    "name": "ChatbotService",
                    "module": "/app/core/services/chat_service.py",
                    "total_connections": 10,
                    "inherits_count": 0,
                    "uses_count": 10,
                    "description": "Service for handling chatbot conversations"
                },
                {
                    "name": "CodebaseIndexer",
                    "module": "/app/core/services/indexing_service.py",
                    "total_connections": 7,
                    ...
                }
            ],
            "threshold": 3
        }
    """
    
    try:
        # Use EnhancedProjectAnalyzer for full analysis
        analyzer = EnhancedProjectAnalyzer(path)
        result = analyzer.analyze()
        
        if not result.get('relationships'):
            return {
                "success": False,
                "error": "No relationships found in project"
            }
        
        relationships = result['relationships']
        
        # Calculate connections for each class
        core_classes = []
        
        for class_name, class_info in relationships.items():
            inherits_count = len(class_info.get('inherits', []))
            uses_count = len(class_info.get('uses', []))
            
            # Calculate "used by" count if requested
            used_by_count = 0
            if include_metrics:
                for other_class, other_info in relationships.items():
                    if class_name in other_info.get('uses', []):
                        used_by_count += 1
            
            total_connections = inherits_count + uses_count
            
            # Filter by minimum connections
            if total_connections >= min_connections:
                class_data = {
                    "name": class_name,
                    "module": class_info.get('module', 'unknown'),
                    "total_connections": total_connections,
                    "inherits_count": inherits_count,
                    "uses_count": uses_count,
                    "description": class_info.get('description', None)
                }
                
                if include_metrics:
                    class_data["used_by_count"] = used_by_count
                    class_data["is_dependency"] = used_by_count > 0
                    class_data["is_leaf"] = uses_count == 0 and inherits_count == 0
                
                core_classes.append(class_data)
        
        # Sort by total connections (most connected first)
        core_classes.sort(key=lambda x: x['total_connections'], reverse=True)
        
        return {
            "success": True,
            "total_classes": len(relationships),
            "core_classes": core_classes,
            "core_count": len(core_classes),
            "threshold": min_connections,
            "coverage_percentage": round((len(core_classes) / len(relationships)) * 100, 1),
            "error": None
        }
        
    except Exception as e:
        logger.error(f"Error getting core classes: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to analyze core classes: {str(e)}"
        }


def search_by_pattern(
    path: str,
    pattern_type: str,
    include_evidence: bool = True
) -> dict:
    """
    Find classes matching design patterns.
    
    **Supported patterns:**
    - "factory": Classes with create/build/get_* methods
    - "singleton": Classes with _instance or get_instance
    - "repository": Django models with .objects manager
    - "service": Classes ending in 'Service' with business logic
    - "serializer": DRF serializers (inherit from Serializer)
    - "viewset": DRF viewsets (inherit from ViewSet)
    - "admin": Django admin classes (inherit from ModelAdmin)
    - "visitor": Classes inheriting from NodeVisitor/Visitor
    - "strategy": Multiple classes with same interface
    
    **Use when:**
    - "Find all Factory classes"
    - "Show me repositories"
    - Understanding architectural patterns
    - Code review / pattern validation
    
    Args:
        path: Project root path
        pattern_type: One of the supported patterns above
        include_evidence: Include why class matches pattern
        
    Returns:
        {
            "success": bool,
            "pattern": str,
            "matches": [
                {
                    "name": str,
                    "module": str,
                    "confidence": "high" | "medium" | "low",
                    "evidence": [str],  # Why it matches (if include_evidence)
                    "description": str
                }
            ],
            "total_matches": int,
            "error": str | None
        }
    
    Example:
        >>> search_by_pattern("/app", "factory")
        {
            "success": True,
            "pattern": "factory",
            "matches": [
                {
                    "name": "LLMFactory",
                    "module": "/app/core/llm_factory/factory.py",
                    "confidence": "high",
                    "evidence": [
                        "Has get_langchain_llm method",
                        "Has get_llama_index_llm method",
                        "Name ends with 'Factory'"
                    ]
                }
            ],
            "total_matches": 2
        }
    """
    
    SUPPORTED_PATTERNS = {
        'factory', 'singleton', 'repository', 'service', 
        'serializer', 'viewset', 'admin', 'visitor', 'strategy'
    }
    
    pattern_type = pattern_type.lower()
    
    if pattern_type not in SUPPORTED_PATTERNS:
        return {
            "success": False,
            "error": f"Unsupported pattern: {pattern_type}. Supported: {', '.join(SUPPORTED_PATTERNS)}"
        }
    
    try:
        # Get full analysis
        analyzer = EnhancedProjectAnalyzer(path)
        result = analyzer.analyze()
        
        if not result.get('relationships'):
            return {
                "success": False,
                "error": "No classes found in project"
            }
        
        relationships = result['relationships']
        matches = []
        
        # Pattern detection logic
        for class_name, class_info in relationships.items():
            evidence = []
            confidence = "low"
            
            bases = class_info.get('inherits', [])
            methods = class_info.get('methods', [])
            module = class_info.get('module', '')
            
            # FACTORY PATTERN
            if pattern_type == 'factory':
                factory_methods = [m for m in methods if m.startswith(('create', 'build', 'get_', 'make'))]
                
                if 'Factory' in class_name:
                    evidence.append(f"Name contains 'Factory'")
                    confidence = "high"
                
                if len(factory_methods) >= 2:
                    evidence.append(f"Has {len(factory_methods)} factory methods: {', '.join(factory_methods[:3])}")
                    if confidence == "low":
                        confidence = "medium"
                
                if factory_methods and 'Factory' in class_name:
                    confidence = "high"
            
            # SINGLETON PATTERN
            elif pattern_type == 'singleton':
                if 'get_instance' in methods or '_instance' in methods:
                    evidence.append("Has get_instance or _instance method")
                    confidence = "high"
                
                if '__new__' in methods:
                    evidence.append("Overrides __new__ (possible singleton)")
                    confidence = "medium"
            
            # REPOSITORY PATTERN (Django)
            elif pattern_type == 'repository':
                if 'Model' in bases:
                    evidence.append("Inherits from Model")
                    confidence = "high"
                
                # Check if it's a Django model with .objects
                if 'models.Model' in str(bases):
                    evidence.append("Django Model with objects manager")
                    confidence = "high"
            
            # SERVICE PATTERN
            elif pattern_type == 'service':
                if class_name.endswith('Service'):
                    evidence.append("Name ends with 'Service'")
                    confidence = "high"
                
                if 'service' in module.lower():
                    evidence.append("Located in services module")
                    if confidence == "low":
                        confidence = "medium"
                
                # Services usually have business logic methods
                business_methods = [m for m in methods if not m.startswith('_')]
                if len(business_methods) >= 3:
                    evidence.append(f"Has {len(business_methods)} public methods")
            
            # SERIALIZER PATTERN (DRF)
            elif pattern_type == 'serializer':
                if 'Serializer' in class_name:
                    evidence.append("Name contains 'Serializer'")
                    confidence = "high"
                
                if any('Serializer' in base for base in bases):
                    evidence.append(f"Inherits from Serializer: {', '.join(bases)}")
                    confidence = "high"
            
            # VIEWSET PATTERN (DRF)
            elif pattern_type == 'viewset':
                if 'ViewSet' in class_name:
                    evidence.append("Name contains 'ViewSet'")
                    confidence = "high"
                
                if any('ViewSet' in base for base in bases):
                    evidence.append(f"Inherits from ViewSet: {', '.join(bases)}")
                    confidence = "high"
            
            # ADMIN PATTERN (Django)
            elif pattern_type == 'admin':
                if 'Admin' in class_name:
                    evidence.append("Name contains 'Admin'")
                    confidence = "high"
                
                if any('ModelAdmin' in base or 'Admin' in base for base in bases):
                    evidence.append(f"Inherits from ModelAdmin: {', '.join(bases)}")
                    confidence = "high"
            
            # VISITOR PATTERN
            elif pattern_type == 'visitor':
                if 'Visitor' in class_name:
                    evidence.append("Name contains 'Visitor'")
                    confidence = "high"
                
                if any('Visitor' in base for base in bases):
                    evidence.append(f"Inherits from Visitor: {', '.join(bases)}")
                    confidence = "high"
                
                visit_methods = [m for m in methods if m.startswith('visit_')]
                if len(visit_methods) >= 2:
                    evidence.append(f"Has {len(visit_methods)} visit_* methods")
                    if confidence == "low":
                        confidence = "medium"
            
            # STRATEGY PATTERN (detected across multiple classes)
            elif pattern_type == 'strategy':
                # Strategy pattern needs comparison across classes
                # This is more complex - simplified version
                if len(bases) > 0:
                    # Classes implementing same interface
                    shared_methods = set(methods)
                    for other_class, other_info in relationships.items():
                        if other_class != class_name and set(bases) == set(other_info.get('inherits', [])):
                            other_methods = set(other_info.get('methods', []))
                            if len(shared_methods & other_methods) >= 3:
                                evidence.append(f"Shares interface with {other_class}")
                                confidence = "medium"
            
            # Add to matches if evidence found
            if evidence:
                match_data = {
                    "name": class_name,
                    "module": module,
                    "confidence": confidence,
                    "description": class_info.get('description', None)
                }
                
                if include_evidence:
                    match_data["evidence"] = evidence
                
                matches.append(match_data)
        
        confidence_order = {"high": 0, "medium": 1, "low": 2}
        matches.sort(key=lambda x: confidence_order[x['confidence']])
        
        return {
            "success": True,
            "pattern": pattern_type,
            "matches": matches,
            "total_matches": len(matches),
            "total_classes_analyzed": len(relationships),
            "error": None
        }
        
    except Exception as e:
        logger.error(f"Error searching for pattern {pattern_type}: {e}", exc_info=True)
        return {
            "success": False,
            "pattern": pattern_type,
            "error": f"Pattern search failed: {str(e)}"
        }
    
if __name__ == "__main__":
    # Example usage
    from pprint import pprint
    result = analyze_file("/app/core/services/chat_service.py")
    pprint(result)



