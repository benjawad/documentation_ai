import ast
import json
import sys 
from pathlib import Path
import re
import os 
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage
sys.path.insert(0, str(Path(__file__).parent.parent))


class ArchitectureVisitor(ast.NodeVisitor):
    def __init__(self):
        self.structure = []
        self.class_stack = [] 
        self.global_functions = []

    def visit_ClassDef(self, node):
        class_info = {
            "name": node.name,
            "type": "class",
            "bases": [self._get_id(b) for b in node.bases],
            "methods": [],
            "attributes": {},
            # Optional: Capture class docstrings too if you want full context
            "description": ast.get_docstring(node) 
        }
        self.class_stack.append(class_info)
        self.generic_visit(node)
        
        # Post-process: Convert attributes dict back to list for JSON
        completed_class = self.class_stack.pop()
        completed_class["attributes"] = sorted(
            [{"name": k, "type": v} for k, v in completed_class["attributes"].items()],
            key=lambda x: x['name']
        )
        self.structure.append(completed_class)

    def visit_FunctionDef(self, node):
        is_method = len(self.class_stack) > 0
        
        # 1. Capture Arguments
        current_scope_vars = {}
        args = []
        for arg in node.args.args:
            if arg.arg == 'self': continue
            arg_type = self._get_id(arg.annotation) if arg.annotation else "Unknown"
            args.append(arg.arg)
            current_scope_vars[arg.arg] = arg_type

        if is_method:
            self.class_stack[-1]["_scope"] = current_scope_vars

        # 2. Capture Return Type
        # Logic: If explicitly defined, use it. If missing, set to None (JSON null).
        if node.returns:
            return_type = self._get_id(node.returns)
        else:
            return_type = None  # <--- FIX: Explicitly mark as No Return

        # 3. Capture Description (Docstring)
        description = ast.get_docstring(node) # <--- FIX: Extract description

        method_info = {
            "name": node.name, 
            "args": args, 
            "returns": return_type,
            "description": description # <--- Add to output
        }
        
        if is_method:
            # Handle @property
            if any(isinstance(d, ast.Name) and d.id == 'property' for d in node.decorator_list):
                 # Properties usually return the type they annotate
                 prop_type = return_type if return_type else "Unknown"
                 self._add_attribute(node.name, prop_type)
            else:
                self.class_stack[-1]["methods"].append(method_info)
        else:
            self.global_functions.append(method_info)
            
        self.generic_visit(node)
        
        # Clean up scope
        if is_method and "_scope" in self.class_stack[-1]:
            del self.class_stack[-1]["_scope"]

    def visit_AnnAssign(self, node):
        if not self.class_stack: return
        target = node.target
        attr_name = None
        
        if isinstance(target, ast.Name):
            attr_name = target.id
        elif self._is_self_attribute(target):
            attr_name = target.attr

        if attr_name:
            self._add_attribute(attr_name, self._get_id(node.annotation))

    def visit_Assign(self, node):
        if not self.class_stack: return

        all_targets = self._flatten_targets(node.targets)
        inferred_type = "Unknown"
        
        if isinstance(node.value, ast.Name):
            scope = self.class_stack[-1].get("_scope", {})
            if node.value.id in scope:
                inferred_type = scope[node.value.id] 

        if inferred_type == "Unknown":
            if isinstance(node.value, ast.Call):
                inferred_type = self._get_id(node.value.func)
            elif isinstance(node.value, ast.Constant):
                 inferred_type = type(node.value).__name__ 
            elif isinstance(node.value, ast.List):
                inferred_type = "list"
            elif isinstance(node.value, ast.Dict):
                inferred_type = "dict"

        for target in all_targets:
            if self._is_self_attribute(target):
                self._add_attribute(target.attr, inferred_type)
            elif isinstance(target, ast.Name):
                if "_scope" not in self.class_stack[-1]: 
                     self._add_attribute(target.id, inferred_type)

    def _add_attribute(self, name, type_str):
        existing = self.class_stack[-1]["attributes"].get(name, "Unknown")
        if existing == "Unknown" and type_str != "Unknown":
            self.class_stack[-1]["attributes"][name] = type_str
        elif name not in self.class_stack[-1]["attributes"]:
            self.class_stack[-1]["attributes"][name] = type_str

    def _flatten_targets(self, targets) -> list:
        flat = []
        for t in targets:
            if isinstance(t, (ast.Tuple, ast.List)):
                for elt in t.elts:
                    flat.extend(self._flatten_targets([elt]))
            else:
                flat.append(t)
        return flat

    def _is_self_attribute(self, node) -> bool:
        return (isinstance(node, ast.Attribute) and 
                isinstance(node.value, ast.Name) and 
                node.value.id == 'self')

    def _get_id(self, node) -> str:
        if node is None: return "None"
        if isinstance(node, ast.Name): return node.id
        elif isinstance(node, ast.Attribute):
            val = self._get_id(node.value)
            return f"{val}.{node.attr}" if val else node.attr
        elif isinstance(node, ast.Subscript):
            container = self._get_id(node.value)
            slice_val = self._get_id(node.slice)
            return f"{container}[{slice_val}]"
        elif isinstance(node, ast.Tuple):
            return ", ".join([self._get_id(e) for e in node.elts])
        elif isinstance(node, ast.List):
            return ", ".join([self._get_id(e) for e in node.elts])
        elif isinstance(node, ast.Constant): return str(node.value)
        return "Unknown"
    

    
class FastTypeEnricher:
    """takes the JSON from the Visitor, finds the "Unknown" types, and asks SambaNova to fix them."""

    def __init__(self , llm):
        self.llm = llm
        
    
    def enrich(self, code_context: str, structure: list[dict]) -> list[dict]:
        """
        Scans structure for missing types and asks Llama 3 to infer them.
        """
        missing_vars = []
        
        # 1. Find the gaps (Unknowns or inferred 'Any')
        for cls in structure:
            for attr in cls["attributes"]:
                if attr["type"] in ["Unknown", "Any"]:
                    # We need context: ClassName.AttributeName
                    missing_vars.append(f"{cls['name']}.{attr['name']}")
        
        if not missing_vars:
            return structure 
        # 2. Call SambaNova (The Surgical Strike)
        print(f"⚡ Fast System: Inferring types for {len(missing_vars)} variables...")
        
        prompt = f"""
        Act as a Python Static Analysis Engine.
        The following variables have missing type hints. Infer them based on the code.
        
        Variables to infer: {missing_vars}
        
        Rules:
        1. Return ONLY a valid JSON object.
        2. Keys must be "ClassName.AttributeName".
        3. Values must be the PEP 484 type (e.g., "List[str]", "UserRepository").
        4. If the type is primitive (str, int) or ambiguous, use "Any".
        
        Code Context:
        ```python
        {code_context[:4000]} 
        ```
        """
        
        try:
            messages = [
                SystemMessage(content="You are a JSON-only code analysis tool. Output valid JSON only."),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # 3. Patch the Structure
            content = response.content
            # Clean up potential markdown blocks (```json ... ```)
            if "```" in content:
                content = content.split("```json")[-1].split("```")[0].strip()
            updates = json.loads(content)
            self._apply_patches(structure, updates)
        except Exception as e:
            error_msg = str(e)
            # Check if it's a model not found error
            if "404" in error_msg or "Model not found" in error_msg:
                print(f"⚠️ Model not available on SambaNova. Skipping type enrichment.")
                print(f"   (Tip: Check available models or use Nebius provider)")
            else:
                print(f"⚠️ Enrichment failed: {e}")
            
        return structure

    def _apply_patches(self, structure: list[dict], updates: dict):
        """
        Applies the inferred types back into the Visitor's structure.
        Complexity: O(N*M) but N (classes) and M (attributes) are small.
        """
        for key, inferred_type in updates.items():
            try:
                if "." not in key: continue
                
                class_name, attr_name = key.split(".", 1)
                
                # Find the class
                target_class = next((c for c in structure if c["name"] == class_name), None)
                if target_class:
                    # Find the attribute inside the class
                    for attr in target_class["attributes"]:
                        if attr["name"] == attr_name:
                            print(f"   ✅ Patched {key} -> {inferred_type}")
                            attr["type"] = inferred_type
                            break
            except Exception:
                continue



class DeterministicPlantUMLConverter:
    def convert(self, structure_json: list[dict]) -> str:
        if not structure_json: return ""
        known_classes = {cls["name"] for cls in structure_json}
        lines = ["@startuml", "skinparam linetype ortho"]

        # Draw Classes
        for cls in structure_json:
            lines.append(f"class {cls['name']} {{")
            for attr in cls["attributes"]:
                lines.append(f"  + {attr['name']} : {attr['type']}")
            lines.append("}")

        # Draw Arrows (The Test Subject)
        for cls in structure_json:
            # Inheritance
            for base in cls["bases"]:
                # Clean generics like Repository[Product] -> Repository
                base_clean = base.split("[")[0] 
                if base_clean in known_classes:
                    lines.append(f"{base_clean} <|-- {cls['name']}")

            # Dependencies
            for attr in cls["attributes"]:
                for target in known_classes:
                    if target == cls["name"]: continue
                    
                    # [CRITICAL REGEX]
                    # \b ensures we match "Product" but NOT "ProductionConfig"
                    pattern = fr"\b{re.escape(target)}\b"
                    
                    if re.search(pattern, attr["type"]):
                        lines.append(f"{cls['name']} o-- {target} : {attr['name']}")
                        break 

        lines.append("@enduml")
        return "\n".join(lines)




test_code = """
from typing import List, Dict, Optional, Union, Any, TypeVar, Generic
from abc import ABC, abstractmethod
import datetime

# [COMPLEXITY 1] Generics & Abstractions
T = TypeVar("T")

class Repository(Generic[T], ABC):
    @abstractmethod
    def save(self, entity: T) -> None:
        pass

class LoggableMixin:
    def log(self, msg: str):
        print(f"[LOG] {msg}")

# [COMPLEXITY 2] Domain Models
class Product:
    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price

class User:
    def __init__(self, uid: str):
        self.uid = uid

# [COMPLEXITY 3] Naming Collision Trap for Regex
# Your regex must NOT draw an arrow from 'Product' to 'ProductionConfig'
class ProductionConfig:
    def __init__(self):
        self.env = "PROD"
        self.retries = 3

# [COMPLEXITY 4] Infrastructure Layer
class PostgresConnection:
    def connect(self):
        pass

class RedisCache:
    def set(self, key, val):
        pass

# [COMPLEXITY 5] Implementation with Mixins
class SqlProductRepository(Repository[Product], LoggableMixin):
    def __init__(self, db_conn):
        # [TRAP] Untyped Dependency!
        # The AI Enricher should infer that 'db_conn' is 'PostgresConnection' 
        # based on usage or naming convention.
        self.db = db_conn 
        
    def save(self, entity: Product) -> None:
        self.log(f"Saving {entity.name}")

# [COMPLEXITY 6] The Service Layer (The Spiderweb)
class ECommerceService:
    def __init__(self, repo: SqlProductRepository, config: ProductionConfig):
        # Typed Dependency (Easy for Visitor)
        self.repository: SqlProductRepository = repo
        self.config: ProductionConfig = config
        
        # [TRAP] Constructor Inference
        # Visitor should see this is a 'RedisCache'
        self.cache = RedisCache()
        
        # [TRAP] Complex Nested Type
        # A Dictionary mapping User IDs to a List of Products
        self.cart_state: Dict[str, List[Product]] = {}
        
        # [TRAP] Forward Reference (String literal)
        # Common in Django/FastAPI. Visitor needs to handle string 'User'
        self.current_admin: Optional['User'] = None
        
        # [TRAP] Union Type
        self.last_error: Union[ValueError, ConnectionError, None] = None

    def checkout(self, user_id: str) -> bool:
        return True
"""

test_2 = """
from typing import List, Dict, Union, Optional, TypeVar, Generic, Callable
from abc import ABC, abstractmethod
import datetime

T = TypeVar("T")
U = TypeVar("U")

# --------------------------
# Mixins, Multiple Inheritance
# --------------------------
class TimestampMixin:
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    def touch(self):
        self.updated_at = datetime.datetime.now()

class LoggingMixin:
    def log(self, msg: str):
        print(f"[LOG] {msg}")

# --------------------------
# Abstract & Generic Repositories
# --------------------------
class Repository(ABC, Generic[T]):
    @abstractmethod
    def save(self, entity: T) -> None:
        pass

class AuditableRepository(Repository[T], TimestampMixin):
    def audit(self, entity: T):
        self.touch()

# --------------------------
# Domain Models with nested attributes
# --------------------------
class Product:
    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price
        self.tags: Optional[List[str]] = None
        self.metadata: Dict[str, Union[str, int, float]] = {}

class User:
    def __init__(self, uid: str):
        self.uid = uid
        self.purchase_history: List['Product'] = []

class Admin(User, LoggingMixin):
    def __init__(self, uid: str, level: int):
        super().__init__(uid)
        self.level = level
        self.permissions: Dict[str, bool] = {}

# --------------------------
# Edge Cases: naming collisions
# --------------------------
class ProductConfig:
    def __init__(self):
        self.env = "PROD"
        self.retries = 3

class Product:
    def __init__(self):
        self.code = "X123"

# --------------------------
# Complex Services Layer
# --------------------------
class ECommerceService:
    def __init__(self, repo: AuditableRepository['Product'], cache):
        self.repo: AuditableRepository['Product'] = repo
        self.cache = cache
        self.cart_state: Dict[str, List[Product]] = {}
        self.admin: Optional[Admin] = None
        self.last_error: Union[ValueError, KeyError, None] = None

    def checkout(self, user_id: str) -> bool:
        if user_id not in self.cart_state:
            self.last_error = KeyError("User cart missing")
            return False
        return True

    def add_product(self, user_id: str, product: Product):
        self.cart_state.setdefault(user_id, []).append(product)

# --------------------------
# Infrastructure Layer
# --------------------------
class RedisCache:
    def __init__(self, host: str = "localhost", port: int = 6379):
        self.host = host
        self.port = port
        self.store: Dict[str, object] = {}

    def set(self, key: str, val: object):
        self.store[key] = val

    def get(self, key: str) -> object:
        return self.store.get(key)

class PostgresConnection:
    def connect(self):
        pass

# --------------------------
# Implementation & Dependency Injection
# --------------------------
class ProductRepository(AuditableRepository[Product], LoggingMixin):
    def __init__(self, conn: PostgresConnection, cache: RedisCache):
        self.db = conn
        self.cache = cache

    def save(self, entity: Product) -> None:
        self.log(f"Saving {entity}")
        self.db.connect()

# --------------------------
# Boilerplate Factory Patterns
# --------------------------
class RepositoryFactory:
    @staticmethod
    def create_product_repo(conn: PostgresConnection, cache: RedisCache) -> ProductRepository:
        return ProductRepository(conn, cache)

class ServiceFactory:
    @staticmethod
    def create_ecommerce_service(repo: AuditableRepository[Product], cache: RedisCache) -> ECommerceService:
        return ECommerceService(repo, cache)

# --------------------------
# Dynamic & Callable Attributes
# --------------------------
class DynamicAttributes:
    def __init__(self):
        self._handlers: Dict[str, Callable[[int], int]] = {}
        for name in ["add", "multiply"]:
            self._handlers[name] = getattr(self, f"_{name}_impl")

    def _add_impl(self, x: int) -> int:
        return x + 1

    def _multiply_impl(self, x: int) -> int:
        return x * 2


"""
test_1 = """
import ast
import json
from typing import List, Dict, Union, Optional, Callable, NewType
from abc import ABC

# [HARD] 1. Dynamic Base Classes & Aliasing
# AST visitors often fail to resolve 'Base' when it's conditional or aliased
DEBUG = True
Base = object if DEBUG else ABC

# [HARD] 2. Type Aliases
# Visitor needs to resolve 'UserId' to 'int' or keep it as a domain type
UserId = NewType('UserId', int)

class ComplexSystem(Base):
    # [HARD] 3. Class-Level Attributes (Static Fields)
    # Your current code only looks for 'self.var' inside methods.
    # It will likely MISS 'version' and 'config'.
    version: str = "1.0.0"
    config = {"timeout": 30}

    def __init__(self):
        # [HARD] 4. Tuple Unpacking Assignment
        # AST represents this as a Tuple node, not a direct Attribute.
        # Your visitor will likely CRASH or MISS 'x' and 'y'.
        self.x, self.y = (10.0, 20.0)

        # [HARD] 5. Chained Assignments
        # Resolving 'self.a' and 'self.b' simultaneously
        self.a = self.b = 0

        # [HARD] 6. Binary Operations / Complex Values
        # Your code ignores 'BinOp' (math) and non-Call/Constant values.
        # This attribute will be inferred as "Unknown" or ignored entirely.
        self.calculated_val = 100 * 5 + 2

        # [HARD] 7. List/Dict Comprehensions
        # Common pattern, but complex AST node structure (ListComp).
        self.squared_map = {i: i*i for i in range(10)}

        # [HARD] 8. Lambda Functions
        # 'self.handler' is a function, but assigned as a variable.
        self.handler = lambda x: x + 1

    def dynamic_loader(self):
        # [HARD] 9. Dynamic Attribute Injection (setattr)
        # Static analysis CANNOT easily see 'self.plugin'.
        # This requires symbolic execution or very specific pattern matching.
        setattr(self, "plugin", "LoadedPlugin")

    @property
    def status(self) -> str:
        # [HARD] 10. Properties
        # Is this a method or an attribute? PlantUML usually treats properties
        # as attributes, but AST sees a FunctionDef with a decorator.
        return "Active"

    def complex_typing(self, data: Dict[UserId, List[Union[str, 'ComplexSystem']]]):
        # [HARD] 11. Forward References & Quotes
        # 'ComplexSystem' is quoted (forward ref) and recursive.
        pass

# [HARD] 12. Inner Classes
# Classes defined inside other scopes.
# Your visitor tracks 'current_class' globally; nesting might overwrite state.
class Outer:
    class Inner:
        def __init__(self):
            self.inner_var = 1

"""
test = """

from typing import (
    List, Dict, Set, Tuple, Union, Optional, Any, TypeVar, Generic,
    Callable, Protocol, Literal, TypedDict, ClassVar, Final,
    Annotated, overload, TYPE_CHECKING
)
from abc import ABC, abstractmethod, ABCMeta
from dataclasses import dataclass, field
from collections.abc import Iterable, Mapping
from enum import Enum, auto
import sys
import asyncio
from contextlib import contextmanager

if TYPE_CHECKING:
    from datetime import datetime

# ============================================================================
# SECTION 1: TYPE SYSTEM NIGHTMARES
# ============================================================================

T = TypeVar('T')
U = TypeVar('U', bound='BaseEntity')
V = TypeVar('V', int, str)  # Constrained TypeVar
Numeric = TypeVar('Numeric', int, float, complex)

# Recursive type alias
JsonValue = Union[None, bool, int, float, str, List['JsonValue'], Dict[str, 'JsonValue']]

# Protocol (structural typing)
class Comparable(Protocol):
    def __lt__(self, other: Any) -> bool: ...

# TypedDict
class UserDict(TypedDict, total=False):
    id: int
    name: str
    metadata: Dict[str, Any]

# Literal types
Mode = Literal['read', 'write', 'append']

# ============================================================================
# SECTION 2: METACLASS & DYNAMIC CLASS CONSTRUCTION
# ============================================================================

class SingletonMeta(type):
    _instances: Dict[type, Any] = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

# Dynamic base selection
DEBUG_MODE = True
RuntimeBase = ABC if DEBUG_MODE else object

class DynamicInheritance(RuntimeBase, metaclass=ABCMeta):
    
    pass

# ============================================================================
# SECTION 3: EXTREME ATTRIBUTE ASSIGNMENT PATTERNS
# ============================================================================

@dataclass
class ComplexEntity:
    # Dataclass fields (ignored by normal AST visitors)
    id: int
    name: str = field(default="Unknown")
    tags: List[str] = field(default_factory=list)
    metadata: ClassVar[Dict[str, Any]] = {}  # Class variable
    _internal: int = field(default=0, init=False, repr=False)
    
    def __post_init__(self):
        # Post-initialization attributes
        self.computed_hash = hash(self.name)
        object.__setattr__(self, 'frozen_val', 42)  # Bypassing frozen dataclass

class AttributeChaos:
    # Class-level type hints without values
    class_var: ClassVar[int]
    annotated_only: str
    
    # Class-level with values
    VERSION: Final[str] = "2.0.0"
    config = {"nested": {"deep": {"value": 1}}}
    
    def __init__(self, x: int, y: str, *args, **kwargs):
        # 1. Multiple unpacking patterns
        self.a, self.b, *self.rest = [1, 2, 3, 4, 5]
        
        # 2. Nested tuple unpacking
        (self.x1, self.y1), (self.x2, self.y2) = ((1, 2), (3, 4))
        
        # 3. Starred expression
        *self.prefix, self.last = range(10)
        
        # 4. Walrus operator in assignment
        if (self.cached := self._expensive_call()) > 10:
            self.threshold = self.cached * 2
        
        # 5. Chained assignments
        self.alpha = self.beta = self.gamma = []
        
        # 6. Dictionary unpacking
        defaults = {'timeout': 30, 'retries': 3}
        self.__dict__.update(**defaults)  # Dynamic attributes!
        
        # 7. Conditional assignment
        self.value = x if x > 0 else y
        
        # 8. Complex expressions
        self.computed = (x ** 2 + y.__len__()) / max(args, default=1)
        
        # 9. Lambda
        self.transformer: Callable[[int], int] = lambda n: n * 2
        
        # 10. Comprehensions
        self.squares = {i: i**2 for i in range(10)}
        self.filtered = [x for x in args if isinstance(x, int)]
        
        # 11. Generator expression (NOT a list)
        self.lazy_gen = (x for x in range(1000))
        
        # 12. Set and dict
        self.unique_items = {*args, *kwargs.values()}
        
        # 13. Slice assignment
        self.buffer = [0] * 100
        self.buffer[10:20] = [1] * 10
        
        # 14. Augmented assignment
        self.counter = 0
        self.counter += 1
        self.counter *= 2
        
        # 15. Dynamic attribute names
        for key in kwargs:
            setattr(self, f"dynamic_{key}", kwargs[key])
    
    def _expensive_call(self):
        return 42
    
    @property
    def smart_property(self) -> int:
        return self.counter
    
    @smart_property.setter
    def smart_property(self, value: int):
        self.counter = value
    
    @smart_property.deleter
    def smart_property(self):
        del self.counter

# ============================================================================
# SECTION 4: INHERITANCE NIGHTMARES
# ============================================================================

class Mixin1:
    def m1(self): pass

class Mixin2:
    def m2(self): pass

class Mixin3:
    def m3(self): pass

# Multiple inheritance with method resolution order complexity
class MultiInherit(Mixin1, Mixin2, Mixin3, DynamicInheritance):
    
    pass

# Generic with multiple type parameters and constraints
class Repository(Generic[T, U], ABC):
    items: Dict[int, T]
    
    @abstractmethod
    def save(self, item: T) -> U: ...

class CachedRepository(Repository[T, U], Mixin1):
    def __init__(self):
        self.cache: Dict[str, T] = {}
        self.items: Dict[int, T] = {}  # Overriding parent type hint

# Nested generic inheritance
class SpecializedRepo(CachedRepository[ComplexEntity, 'OperationResult']):
    def __init__(self, conn: 'DatabaseConnection'):
        super().__init__()
        self.connection = conn  # Type inference needed!

# ============================================================================
# SECTION 5: FORWARD REFERENCES & CIRCULAR DEPENDENCIES
# ============================================================================

class Node:
    def __init__(self, value: int):
        self.value = value
        self.children: List['Node'] = []  # Self-reference
        self.parent: Optional['Node'] = None
        self.sibling: Union['Node', 'Leaf', None] = None  # Cross-reference

class Leaf:
    def __init__(self):
        self.attached_node: Optional[Node] = None

class Tree:
    def __init__(self):
        self.root: 'Node' = Node(0)  # Forward ref in quotes
        self.registry: Dict[int, Union[Node, Leaf]] = {}
        
        # Circular reference nightmare
        self.metadata: 'TreeMetadata' = None  # type: ignore

class TreeMetadata:
    def __init__(self, tree: Tree):
        self.parent_tree = tree

# ============================================================================
# SECTION 6: ADVANCED TYPE ANNOTATIONS
# ============================================================================

class AdvancedTypes:
    # Annotated with metadata
    user_id: Annotated[int, "Must be positive"]
    
    # Callable with complex signature
    callback: Callable[[int, str], Tuple[bool, Optional[str]]]
    
    # Nested generics
    matrix: List[List[List[float]]]
    
    # Union of generics
    storage: Union[Dict[str, List[int]], Set[Tuple[str, int]]]
    
    # Optional nested
    maybe_nested: Optional[Dict[str, Optional[List[Optional[int]]]]]
    
    # Generic protocol
    comparator: Comparable
    
    # Literal union
    status: Union[Literal['pending'], Literal['active'], Literal['done']]
    
    def __init__(self):
        # Type narrowing scenarios
        self.value: Union[int, str] = 42
        if isinstance(self.value, int):
            self.numeric_value = self.value  # Should infer as int
        
        # Complex callable assignment
        self.processor: Callable[[JsonValue], JsonValue] = lambda x: x

# ============================================================================
# SECTION 7: SPECIAL METHODS & DESCRIPTORS
# ============================================================================

class Descriptor:
    def __get__(self, obj, objtype=None):
        return 42
    
    def __set__(self, obj, value):
        pass

class SpecialMethods:
    managed_attr = Descriptor()  # Descriptor protocol
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
    
    def __getattr__(self, name: str):
        # Dynamic attribute access
        return self._data.get(name)
    
    def __setattr__(self, name: str, value: Any):
        if name == '_data':
            object.__setattr__(self, name, value)
        else:
            self._data[name] = value
    
    def __getitem__(self, key: str) -> Any:
        return self._data[key]
    
    def __setitem__(self, key: str, value: Any):
        self._data[key] = value

# ============================================================================
# SECTION 8: ASYNC & CONTEXT MANAGERS
# ============================================================================

class AsyncResource:
    def __init__(self):
        self.connection: Optional['AsyncConnection'] = None
    
    async def __aenter__(self) -> 'AsyncResource':
        self.connection = await self._connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.connection.close()
    
    async def _connect(self) -> 'AsyncConnection':
        return AsyncConnection()

class AsyncConnection:
    async def close(self):
        pass

# ============================================================================
# SECTION 9: ENUMS & SPECIAL CLASSES
# ============================================================================

class Status(Enum):
    PENDING = auto()
    ACTIVE = auto()
    DONE = auto()
    
    def describe(self) -> str:
        return self.name.lower()

# ============================================================================
# SECTION 10: NAMING COLLISION TRAPS
# ============================================================================

class Product:
    
    def __init__(self, name: str):
        self.name = name
        self.price: float = 0.0

class ProductConfig:
    
    def __init__(self):
        self.env = "production"

class ProductionManager:
    
    def __init__(self):
        self.products: List[Product] = []  # This SHOULD have arrow
        self.config = ProductConfig()  # This SHOULD have arrow

class ProductFactory:
    
    @staticmethod
    def create(name: str) -> Product:
        return Product(name)

# ============================================================================
# SECTION 11: DEPENDENCY INJECTION & CONSTRUCTOR COMPLEXITY
# ============================================================================

class DatabaseConnection:
    pass

class CacheLayer:
    pass

class Logger:
    pass

class MessageQueue:
    pass

class ComplexService:
    def __init__(
        self,
        db: DatabaseConnection,
        cache: CacheLayer,
        logger: Logger,
        queue: MessageQueue,
        config: Optional[ProductConfig] = None,
        *middleware,
        **options
    ):
        # Should infer all of these types from constructor args!
        self.database = db
        self.cache_layer = cache
        self.log = logger
        self.mq = queue
        
        # Optional should be preserved
        self.configuration = config
        
        # Args/kwargs - harder to type
        self.middleware_stack = list(middleware)
        self.runtime_options = options
        
        # Nested dependency
        self.fallback_cache = CacheLayer()  # Direct instantiation
        
        # Complex initialization
        self.connection_pool: List[DatabaseConnection] = [
            DatabaseConnection() for _ in range(3)
        ]

# ============================================================================
# SECTION 12: OVERLOADED METHODS
# ============================================================================

class OverloadExample:
    @overload
    def process(self, data: int) -> str: ...
    
    @overload
    def process(self, data: str) -> int: ...
    
    def process(self, data: Union[int, str]) -> Union[str, int]:
        if isinstance(data, int):
            return str(data)
        return len(data)

# ============================================================================
# SECTION 13: INNER CLASSES & NESTED SCOPES
# ============================================================================

class Outer:
    outer_class_var: ClassVar[int] = 1
    
    class Inner:
        inner_var: str = "test"
        
        def __init__(self):
            self.instance_var = 42
        
        class DeepInner:
            def __init__(self):
                self.deep_value = "nested"
    
    def __init__(self):
        self.inner_instance = self.Inner()
        self.deep = self.Inner.DeepInner()

# ============================================================================
# SECTION 14: EDGE CASES THAT COMMONLY BREAK PARSERS
# ============================================================================

class EdgeCases:
    def __init__(self):
        # Attribute on method call result
        self.length = "hello".upper().__len__()
        
        # Subscript on attribute
        self.data_point = {"key": [1, 2, 3]}["key"][0]
        
        # Multiple attribute access
        self.nested_value = ComplexEntity(1).metadata.get("key", {})
        
        # Conditional expression in type position (won't work but tests parser)
        self.dynamic_type = int if True else str
        
        # Star unpacking in different contexts
        self.unpacked_dict = {**{"a": 1}, **{"b": 2}}
        self.unpacked_list = [*range(5), *range(5, 10)]
        
        # f-string (should be treated as str)
        name = "test"
        self.formatted = f"Hello {name}"
        
        # Bytes and raw strings
        self.binary = b"binary data"
        self.raw = 'raw\nstring'
        
        # Ellipsis
        self.placeholder = ...
        
        # Complex slice
        self.multi_slice = [[1, 2], [3, 4]][0:1][0]

# ============================================================================
# SECTION 15: THE FINAL BOSS - EVERYTHING COMBINED
# ============================================================================

class FinalBoss(
    Repository[ComplexEntity, 'OperationResult'],
    Mixin1,
    Mixin2,
    Generic[T],
    metaclass=SingletonMeta
):
    
    # Class variables with complex types
    REGISTRY: ClassVar[Dict[str, 'FinalBoss']] = {}
    _cache: ClassVar[Optional[CacheLayer]] = None
    
    def __init__(
        self,
        primary_db: DatabaseConnection,
        *secondary_dbs: DatabaseConnection,
        cache: Optional[CacheLayer] = None,
        **options: Union[str, int, bool]
    ):
        # Constructor type inference
        self.primary = primary_db
        self.secondaries = list(secondary_dbs)
        self.cache_instance = cache or CacheLayer()
        
        # Complex unpacking
        self.x, *self.middle, self.z = range(100)
        
        # Nested types
        self.graph: Dict[Node, List[Tuple[Node, float]]] = {}
        
        # Forward reference with generics
        self.results: List['OperationResult[ComplexEntity]'] = []
        
        # Union of custom types
        self.state: Union[Product, ComplexEntity, Node] = Product("test")
        
        # Callable with generics
        self.mapper: Callable[[T], Optional[U]] = lambda x: None
        
        # All previous edge cases
        (self.a, self.b), self.c = ((1, 2), 3)
        self.lambda_ref = lambda: self.primary
        self.comprehension = {k: v for k, v in options.items() if isinstance(v, str)}

class OperationResult(Generic[T]):
    def __init__(self, data: T):
        self.data = data
        self.success = True

# ============================================================================
# GLOBAL SCOPE COMPLEXITY
# ============================================================================

def standalone_function(x: ComplexEntity) -> OperationResult[ComplexEntity]:
    return OperationResult(x)

async def async_function(node: Node) -> List[Node]:
    
    return node.children

@contextmanager
def context_function() -> DatabaseConnection:
    
    conn = DatabaseConnection()
    yield conn

# Lambda in global scope
global_lambda: Callable[[int], str] = lambda x: str(x)

# ============================================================================
# TYPE CHECKING ONLY IMPORTS
# ============================================================================

if TYPE_CHECKING:
    # These should be visible to type checkers but not at runtime
    from datetime import datetime
    SpecialDateTime = datetime


"""



if __name__ == "__main__":
    code = """
import os 
class MyClass:
    def sum(self , x,y) -> int: 
        return x + y

def my_global_function(x: int):
    pass

def another_function():
    return True
            """

    print("--- DEBUGGING VISITOR ---")
    tree = ast.parse(test_1)
    visitor = ArchitectureVisitor()
    visitor.visit(tree)

    print(f"Global Functions Found: {len(visitor.global_functions)}")
    for f in visitor.global_functions:
        print(f" - {f['name']}")

    print("\nStructure Output:")
    print(json.dumps(visitor.structure, indent=2))

# if __name__ == "__main__":
#     # Path to your project file
#     filepath = "architecture_service.py"  # Replace with your file path

#     # Read the file content
#     with open(filepath, "r", encoding="utf-8") as f:
#         code = f.read()

#     # Parse AST
#     tree = ast.parse(code)
#     visitor = ArchitectureVisitor()
#     visitor.visit(tree)

#     # Print global functions
#     print(f"Global Functions Found: {len(visitor.global_functions)}")
#     for f in visitor.global_functions:
#         print(f" - {f['name']}")

#     # Print class structure
#     print("\nStructure Output:")
#     print(json.dumps(visitor.structure, indent=2))
