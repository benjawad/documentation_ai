# Architecture Analysis Summary

## Overview
- **Total Classes**: 9
- **Inheritance Relationships**: 2
- **Dependency Relationships**: 19
- **Core Classes**: 9

## Core Classes (Most Connected)

### RelationshipExtractor
- **Module**: `/app/core/services/relationship_service.py`
- **Connections**: 5
- **Uses**: ClassRelationship, Dict[str, Dict], List[str], Optional[str], Set[str]
- **Description**: Extracts relationships from your project JSON.
Works directly with the output of ProjectAnalyzer.

### ClassRelationship
- **Module**: `/app/core/services/relationship_service.py`
- **Connections**: 4
- **Uses**: List[Dict], List[str], Optional[str], Set[str]
- **Description**: Represents relationships for a single class

### FileSystemNode
- **Module**: `/app/core/services/files.py`
- **Connections**: 3
- **Uses**: FileSystemNode, Optional[int], directory

### ProjectAnalyzer
- **Module**: `/app/core/services/project_service.py`
- **Connections**: 3
- **Uses**: Dict[str, Any], FileSystemVisitor, resolve
- **Description**: Orchestrates the analysis.
1. Uses FileSystemVisitor to walk the tree and filter noise.
2. Uses ArchitectureVisitor to parse Python logic found in that tree.

### EnhancedProjectAnalyzer
- **Module**: `/app/core/services/relationship_service.py`
- **Connections**: 2
- **Uses**: ProjectAnalyzer, RelationshipExtractor
- **Description**: Wrapper that adds relationship analysis to your ProjectAnalyzer.

Usage:
    analyzer = EnhancedProjectAnalyzer("/app")
    result = analyzer.analyze()
    
    # result now contains:
    # - 'tree': Original project tree with AST analysis
    # - 'relationships': Class relationships
    # - 'mermaid': Mermaid diagram

### ArchitectureVisitor
- **Module**: `/app/core/services/architecture_service.py`
- **Connections**: 1
- **Inherits**: NodeVisitor

### FastTypeEnricher
- **Module**: `/app/core/services/architecture_service.py`
- **Connections**: 1
- **Uses**: list[dict]
- **Description**: takes the JSON from the Visitor, finds the "Unknown" types, and asks SambaNova to fix them.

### FileSystemVisitor
- **Module**: `/app/core/services/files.py`
- **Connections**: 1
- **Uses**: FileSystemNode
- **Description**: A deterministic visitor for the file system.
IMPROVED: Implements a "VIP Pass" to capture environment context (The Devil's Advocate Fix).

### CoreConfig
- **Module**: `/app/core/apps.py`
- **Connections**: 1
- **Inherits**: AppConfig


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
