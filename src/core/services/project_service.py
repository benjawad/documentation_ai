import os
import ast
import json
import logging
from pathlib import Path
from dataclasses import asdict
from typing import Dict, Any, Optional

from architecture_service import ArchitectureVisitor
from files import FileSystemVisitor

# ==============================================================================
# THE ORCHESTRATOR: Combines Scanning (Chassis) + Parsing (Engine)
# ==============================================================================
class ProjectAnalyzer:
    """
    Orchestrates the analysis.
    1. Uses FileSystemVisitor to walk the tree and filter noise.
    2. Uses ArchitectureVisitor to parse Python logic found in that tree.
    """
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.fs_visitor = FileSystemVisitor() # Your existing class
        
    def analyze(self) -> Dict[str, Any]:
        logging.info(f"📂 Starting deep analysis at: {self.root_path}")
        
        # 1. Get the skeleton (Directory Tree) using your FileSystemVisitor
        # This handles the recursion and ignore lists automatically.
        tree_structure = self.fs_visitor.visit(str(self.root_path), max_depth=10)
        
        if not tree_structure:
            logging.warning("⚠️ Empty tree. Check path or ignore lists.")
            return {}

        # 2. Flesh out the skeleton (Inject AST Analysis)
        # We traverse the clean dictionary returned by FileSystemVisitor
        self._enrich_node_with_ast(tree_structure)
        
        return tree_structure

    def _enrich_node_with_ast(self, node: Dict[str, Any]):
        """
        Recursive function to walk the JSON tree. 
        If it finds a .py file, it runs ArchitectureVisitor and injects the data.
        """
        
        # A. If it's a directory, recurse into children
        if node['type'] == 'directory' and node.get('children'):
            for child in node['children']:
                self._enrich_node_with_ast(child)
                
        # B. If it's a Python file, Analyze it!
        elif node['type'] == 'file' and node['name'].endswith('.py'):
            file_path = Path(node['path'])
            try:
                # Read Code
                with open(file_path, "r", encoding="utf-8") as f:
                    source_code = f.read()
                
                # Run Engine (Your ArchitectureVisitor)
                tree = ast.parse(source_code)
                visitor = ArchitectureVisitor()
                visitor.visit(tree)
                
                # Inject Analysis ONLY if significant logic is found
                if visitor.structure or visitor.global_functions:
                    node['analysis'] = {
                        "classes": visitor.structure,
                        "global_functions": visitor.global_functions,
                        # "imports": visitor.imports # Add this to Visitor if you want imports
                    }
                    logging.info(f"  ✅ Parsed Logic: {node['name']}")
                    
            except Exception as e:
                logging.warning(f"  ⚠️ Failed to parse {node['name']}: {e}")

# ==============================================================================
# EXECUTION ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    # Setup Logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    # 1. Detect Path (Docker or Local)
    target_path = "/app" if Path("/app").exists() else "."
    
    # 2. Run Analysis
    analyzer = ProjectAnalyzer(target_path)
    full_context = analyzer.analyze()

    # 3. Save Result
    output_file = "full_project_context.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(full_context, f, indent=2)

    print(f"\n🎉 Success! Full Context (Tree + Logic) saved to {output_file}")