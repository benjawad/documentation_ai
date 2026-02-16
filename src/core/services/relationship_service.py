"""
Relationship Analyzer for Existing Project JSON
Extracts class relationships from the enriched project tree.

Integrates with:
- ProjectAnalyzer (generates the JSON)
- ArchitectureVisitor (provides class structure)
- FileSystemVisitor (provides file tree)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Set, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class ClassRelationship:
    """Represents relationships for a single class"""
    name: str
    module: str  # File path
    inherits: Set[str] = field(default_factory=set)
    uses: Set[str] = field(default_factory=set)
    methods: List[str] = field(default_factory=list)
    attributes: List[Dict] = field(default_factory=list)
    description: Optional[str] = None


class RelationshipExtractor:
    """
    Extracts relationships from your project JSON.
    Works directly with the output of ProjectAnalyzer.
    """
    
    # Filter out primitive types
    PRIMITIVES = {
        'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple',
        'Any', 'None', 'Optional', 'Union', 'List', 'Dict', 'Set', 'Tuple',
        'Callable', 'Type', 'Unknown', 'Constant'
    }
    
    def __init__(self):
        self.classes: Dict[str, ClassRelationship] = {}
        self.all_class_names: Set[str] = set()
    
    def extract_from_json(self, project_json: Dict) -> Dict[str, ClassRelationship]:
        """
        Extract relationships from your full_project_context.json
        
        Args:
            project_json: The JSON from ProjectAnalyzer.analyze()
        
        Returns:
            Dict of class_name -> ClassRelationship
        """
        logging.info("🔍 Extracting relationships from project JSON...")
        
        # First pass: Collect all class names
        self._collect_class_names(project_json)
        
        # Second pass: Extract relationships
        self._extract_relationships(project_json)
        
        logging.info(f"✅ Found {len(self.classes)} classes with relationships")
        return self.classes
    
    def _collect_class_names(self, node: Dict):
        """First pass: Build index of all class names"""
        if node.get('type') == 'file' and 'analysis' in node:
            for class_info in node['analysis'].get('classes', []):
                self.all_class_names.add(class_info['name'])
        
        # Recurse
        if node.get('children'):
            for child in node['children']:
                self._collect_class_names(child)
    
    def _extract_relationships(self, node: Dict, current_path: str = ""):
        """Second pass: Extract relationships"""
        
        # Update current path
        if node.get('type') == 'directory':
            current_path = node.get('path', current_path)
        
        # Process Python files with analysis
        if node.get('type') == 'file' and 'analysis' in node:
            module_path = node.get('path', 'unknown')
            
            for class_info in node['analysis'].get('classes', []):
                self._process_class(class_info, module_path)
        
        # Recurse into children
        if node.get('children'):
            for child in node['children']:
                self._extract_relationships(child, current_path)
    
    def _process_class(self, class_info: Dict, module_path: str):
        """Process a single class from the JSON"""
        class_name = class_info['name']
        
        rel = ClassRelationship(
            name=class_name,
            module=module_path,
            description=class_info.get('description')
        )
        
        # 1. Extract inheritance
        for base in class_info.get('bases', []):
            base_clean = self._clean_type(base)
            if base_clean and base_clean not in self.PRIMITIVES:
                rel.inherits.add(base_clean)
        
        # 2. Extract composition from attributes
        for attr in class_info.get('attributes', []):
            attr_type = self._clean_type(attr.get('type', 'Unknown'))
            if attr_type and attr_type not in self.PRIMITIVES:
                rel.uses.add(attr_type)
            rel.attributes.append(attr)
        
        # 3. Extract dependencies from methods
        for method in class_info.get('methods', []):
            rel.methods.append(method['name'])
            
            # Extract from return types
            return_type = self._clean_type(method.get('returns'))
            if return_type and return_type not in self.PRIMITIVES:
                rel.uses.add(return_type)
        
        self.classes[class_name] = rel
    
    def _clean_type(self, type_str: Optional[str]) -> Optional[str]:
        """
        Clean type string to extract the core class name.
        
        Examples:
            "Optional[User]" -> "User"
            "List[Product]" -> "Product"
            "ast.NodeVisitor" -> "NodeVisitor"
            "Literal[file, directory]" -> None (ignore)
        """
        if not type_str or type_str in self.PRIMITIVES:
            return None
        
        # Handle generics: List[User], Optional[User], Dict[str, User]
        if '[' in type_str:
            # Extract content between brackets
            import re
            matches = re.findall(r'\[([^\[\]]+)\]', type_str)
            if matches:
                # Get the last non-primitive type
                inner_types = matches[0].split(',')
                for inner in reversed(inner_types):
                    clean = inner.strip()
                    if clean not in self.PRIMITIVES:
                        return clean
        
        # Handle module.Class -> Class
        if '.' in type_str:
            type_str = type_str.split('.')[-1]
        
        # Handle Literal types
        if type_str.startswith('Literal'):
            return None
        
        return type_str if type_str not in self.PRIMITIVES else None
    
    def to_dict(self, filter_orphans: bool = True) -> Dict[str, Dict]:
        """
        Convert to JSON-serializable dict.
        
        Args:
            filter_orphans: Remove classes with no relationships
        """
        result = {}
        
        for class_name, rel in self.classes.items():
            # Filter orphans
            if filter_orphans and not rel.inherits and not rel.uses:
                continue
            
            result[class_name] = {
                "module": rel.module,
                "inherits": sorted(rel.inherits),
                "uses": sorted(rel.uses),
                "methods": rel.methods[:5],  # First 5 methods
                "attributes": rel.attributes[:5],  # First 5 attributes
                "description": rel.description
            }
        
        return result
    
    def to_mermaid(self, focus_on: Optional[List[str]] = None) -> str:
        """
        Generate Mermaid class diagram.
        
        Args:
            focus_on: List of class names to show (None = show all with relationships)
        """
        lines = ["classDiagram"]
        
        # Filter classes to show
        if focus_on:
            classes_to_show = {
                name: rel for name, rel in self.classes.items()
                if name in focus_on
            }
        else:
            # Show only classes with relationships
            classes_to_show = {
                name: rel for name, rel in self.classes.items()
                if rel.inherits or rel.uses
            }
        
        if not classes_to_show:
            return "classDiagram\n    note \"No relationships found\""
        
        # Add class definitions
        for class_name, rel in classes_to_show.items():
            lines.append(f"    class {class_name} {{")
            
            # Add key methods
            for method in rel.methods[:3]:
                lines.append(f"        +{method}()")
            
            lines.append("    }")
        
        lines.append("")
        
        # Add relationships
        for class_name, rel in classes_to_show.items():
            # Inheritance (--|>)
            for parent in rel.inherits:
                # Only show if parent exists in our codebase
                if parent in self.all_class_names or not focus_on:
                    lines.append(f"    {parent} <|-- {class_name}")
            
            # Composition/Dependencies (-->)
            for dependency in rel.uses:
                # Only show if dependency exists in our codebase
                if dependency in self.all_class_names or not focus_on:
                    lines.append(f"    {class_name} --> {dependency}")
        
        return "\n".join(lines)
    
    def get_core_classes(self, min_connections: int = 2) -> List[str]:
        """
        Find core classes (most connected).
        
        Args:
            min_connections: Minimum total relationships
        """
        core = []
        for name, rel in self.classes.items():
            total = len(rel.inherits) + len(rel.uses)
            if total >= min_connections:
                core.append(name)
        
        return sorted(core)


# ==============================================================================
# INTEGRATION WITH YOUR EXISTING CODE
# ==============================================================================

class EnhancedProjectAnalyzer:
    """
    Wrapper that adds relationship analysis to your ProjectAnalyzer.
    
    Usage:
        analyzer = EnhancedProjectAnalyzer("/app")
        result = analyzer.analyze()
        
        # result now contains:
        # - 'tree': Original project tree with AST analysis
        # - 'relationships': Class relationships
        # - 'mermaid': Mermaid diagram
    """
    
    def __init__(self, root_path: str):
        from project_service import ProjectAnalyzer
        
        self.project_analyzer = ProjectAnalyzer(root_path)
        self.relationship_extractor = RelationshipExtractor()
    
    def analyze(self) -> Dict:
        """
        Full analysis with relationships.
        
        Returns:
            {
                'tree': {...},  # Original tree
                'relationships': {...},  # Class relationships
                'mermaid': "...",  # Mermaid diagram
                'core_classes': [...]  # Most connected classes
            }
        """
        logging.info("🚀 Starting enhanced analysis...")
        
        # 1. Get your original analysis
        tree = self.project_analyzer.analyze()
        
        # 2. Extract relationships
        relationships = self.relationship_extractor.extract_from_json(tree)
        
        # 3. Generate diagram (focus on core classes)
        core_classes = self.relationship_extractor.get_core_classes(min_connections=1)
        
        if core_classes:
            logging.info(f"📊 Focusing on {len(core_classes)} core classes")
            mermaid = self.relationship_extractor.to_mermaid(focus_on=core_classes)
        else:
            mermaid = self.relationship_extractor.to_mermaid()
        
        return {
            'tree': tree,
            'relationships': self.relationship_extractor.to_dict(),
            'mermaid': mermaid,
            'core_classes': core_classes
        }
    
    def save_outputs(self, output_dir: str = "."):
        """Save all outputs to files"""
        result = self.analyze()
        output_path = Path(output_dir)
        
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            logging.error(f"❌ Permission denied: Cannot create directory {output_path}")
            return
        except Exception as e:
            logging.error(f"❌ Failed to create directory {output_path}: {e}")
            return
        
        # Save JSON
        try:
            with open(output_path / "full_project_context.json", "w") as f:
                json.dump(result['tree'], f, indent=2)
            logging.info(f"✅ Saved: full_project_context.json")
        except Exception as e:
            logging.error(f"❌ Failed to save full_project_context.json: {e}")
        
        try:
            with open(output_path / "class_relationships.json", "w") as f:
                json.dump(result['relationships'], f, indent=2)
            logging.info(f"✅ Saved: class_relationships.json")
        except Exception as e:
            logging.error(f"❌ Failed to save class_relationships.json: {e}")
        
        # Save Mermaid
        try:
            with open(output_path / "class_diagram.mmd", "w") as f:
                f.write(result['mermaid'])
            logging.info(f"✅ Saved: class_diagram.mmd")
        except Exception as e:
            logging.error(f"❌ Failed to save class_diagram.mmd: {e}")
        
        # Save summary
        try:
            summary = self._generate_summary(result)
            with open(output_path / "architecture_summary.md", "w") as f:
                f.write(summary)
            logging.info(f"✅ Saved: architecture_summary.md")
        except Exception as e:
            logging.error(f"❌ Failed to save architecture_summary.md: {e}")
        
        logging.info(f"\n🎉 All outputs saved to: {output_path}")
    
    def _generate_summary(self, result: Dict) -> str:
        """Generate markdown summary"""
        relationships = result['relationships']
        core = result['core_classes']
        
        total_classes = len(relationships)
        total_inherits = sum(len(r['inherits']) for r in relationships.values())
        total_uses = sum(len(r['uses']) for r in relationships.values())
        
        summary = f"""# Architecture Analysis Summary

## Overview
- **Total Classes**: {total_classes}
- **Inheritance Relationships**: {total_inherits}
- **Dependency Relationships**: {total_uses}
- **Core Classes**: {len(core)}

## Core Classes (Most Connected)

"""
        # Show top 10 core classes
        connections = [
            (name, len(data['inherits']) + len(data['uses']))
            for name, data in relationships.items()
        ]
        connections.sort(key=lambda x: x[1], reverse=True)
        
        for name, count in connections[:10]:
            data = relationships[name]
            summary += f"### {name}\n"
            summary += f"- **Module**: `{data['module']}`\n"
            summary += f"- **Connections**: {count}\n"
            
            if data['inherits']:
                summary += f"- **Inherits**: {', '.join(data['inherits'])}\n"
            
            if data['uses']:
                uses_list = ', '.join(data['uses'][:5])
                if len(data['uses']) > 5:
                    uses_list += f" (+{len(data['uses']) - 5} more)"
                summary += f"- **Uses**: {uses_list}\n"
            
            if data['description']:
                summary += f"- **Description**: {data['description']}\n"
            
            summary += "\n"
        
        summary += """
## Diagrams

- [Class Diagram](class_diagram.mmd) - Paste into [Mermaid Live](https://mermaid.live)
- [Relationships JSON](class_relationships.json) - Full data export
- [Full Project Context](full_project_context.json) - Complete tree with AST analysis

## How to View

### Mermaid Diagram
1. Copy content from `class_diagram.mmd`
2. Go to https://mermaid.live
3. Paste and view

### JSON Data
- Use `class_relationships.json` for programmatic access
- Feed to LLM for architecture analysis
- Use for dependency tracking
"""
        return summary


# ==============================================================================
# CLI USAGE
# ==============================================================================

def main():
    """Command line usage"""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    # Get path from args or use default
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
    else:
        project_path = "/app" if Path("/app").exists() else "."
    
    # Get output directory
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    
    # Run analysis
    analyzer = EnhancedProjectAnalyzer(project_path)
    analyzer.save_outputs(output_dir)


if __name__ == "__main__":
    main()