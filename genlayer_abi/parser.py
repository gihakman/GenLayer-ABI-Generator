"""Python AST parser for GenLayer Intelligent Contracts."""

import ast
import functools
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Param:
    name: str
    type: str
    optional: bool = False
    default: Any = None


@dataclass
class Method:
    name: str
    type: str  # "view" | "write" | "write_payable"
    payable: bool = False
    params: list[Param] = field(default_factory=list)
    returns: str = "None"
    docstring: str = ""


@dataclass
class ContractAbi:
    contract_name: str
    methods: list[Method] = field(default_factory=list)


# Map Python AST type nodes to GenLayer/TypeScript type strings
_TYPE_MAP: dict[str, str] = {
    "str": "str",
    "int": "u256",
    "bool": "bool",
    "float": "f64",
    "bytes": "bytes",
    "dict": "dict",
    "list": "DynArray",
    "tuple": "tuple",
    "Address": "Address",
    "u256": "u256",
    "f64": "f64",
    "DynArray": "DynArray",
    "TreeMap": "TreeMap",
    "None": "None",
}


def _resolve_name(node: ast.AST) -> str:
    """Resolve an AST node to a type name string."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Constant):
        return str(node.value)
    elif isinstance(node, ast.Attribute):
        return f"{_resolve_name(node.value)}.{node.attr}"
    elif isinstance(node, ast.Subscript):
        base = _resolve_name(node.value)
        if isinstance(node.slice, ast.Tuple):
            slice_parts = [_resolve_name(elt) for elt in node.slice.elts]
            return f"{base}<{', '.join(slice_parts)}>"
        else:
            slice_str = _resolve_name(node.slice)
            return f"{base}<{slice_str}>"
    elif isinstance(node, ast.List):
        return f"[{', '.join([_resolve_name(elt) for elt in node.elts])}]"
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _resolve_name(node.left)
        right = _resolve_name(node.right)
        return f"{left} | {right}"
    else:
        return "any"


def _map_type(type_str: str) -> str:
    """Map a Python type string to a GenLayer/TS type string."""
    # Handle union types (Python 3.10+ X | Y syntax)
    if " | " in type_str:
        return " | ".join(_map_type(part.strip()) for part in type_str.split(" | "))
    # Strip generics for base lookup
    base = type_str.split("<")[0].strip()
    mapped = _TYPE_MAP.get(base, base)
    # Reattach generics if present
    if "<" in type_str:
        generics = type_str[type_str.index("<") :]
        return mapped + generics
    return mapped


def _is_contract_class(node: ast.ClassDef) -> bool:
    """Check if a class definition inherits from a Contract base class."""
    for base in node.bases:
        name = _resolve_name(base)
        if name == "Contract" or name.endswith(".Contract"):
            return True
    return False


def _extract_decorator_name(dec: ast.expr) -> str:
    """Extract decorator name from AST node (unwraps calls like @decorator())."""
    if isinstance(dec, ast.Call):
        return _resolve_name(dec.func)
    return _resolve_name(dec)


def _parse_method(func: ast.AsyncFunctionDef | ast.FunctionDef) -> Method | None:
    """Parse a function/method definition into a Method if it has GenLayer decorators."""
    method_type: str | None = None
    payable = False

    for dec in func.decorator_list:
        dec_name = _extract_decorator_name(dec)
        if dec_name == "gl.public.view":
            method_type = "view"
        elif dec_name == "gl.public.write":
            method_type = "write"
        elif dec_name == "gl.public.write.payable":
            method_type = "write"
            payable = True
        elif re.match(r"^public\.(view|write)$", dec_name):
            method_type = dec_name.split(".")[-1]
        elif dec_name == "public.write.payable":
            method_type = "write"
            payable = True

    if method_type is None:
        return None

    params: list[Param] = []

    def _collect_args(
        args_list: list[ast.arg],
        defaults: list[ast.expr],
        start_offset: int = 0,
    ) -> None:
        defaults_offset = len(args_list) - len(defaults)
        for i, arg in enumerate(args_list):
            param_type = "any"
            if arg.annotation:
                param_type = _map_type(_resolve_name(arg.annotation))
            optional = False
            default = None
            if i >= defaults_offset:
                default_node = defaults[i - defaults_offset]
                try:
                    default = ast.literal_eval(default_node)
                except Exception:
                    default = None
                optional = True
            params.append(Param(name=arg.arg, type=param_type, optional=optional, default=default))

    # Skip 'self' from regular positional args
    regular_args = func.args.args[1:] if func.args.args else []

    # positional-only args
    _collect_args(func.args.posonlyargs, func.args.defaults)
    # regular positional args (after self)
    # defaults apply to the tail of (posonlyargs + args)
    posonly_count = len(func.args.posonlyargs)
    args_defaults = func.args.defaults[posonly_count:] if len(func.args.defaults) > posonly_count else []
    _collect_args(regular_args, args_defaults)
    # *args
    if func.args.vararg:
        v = func.args.vararg
        vtype = _map_type(_resolve_name(v.annotation)) if v.annotation else "any"
        params.append(Param(name=v.arg, type=f"...{vtype}", optional=True, default=None))
    # keyword-only args
    kw_defaults = func.args.kw_defaults if func.args.kw_defaults else []
    for i, arg in enumerate(func.args.kwonlyargs):
        param_type = "any"
        if arg.annotation:
            param_type = _map_type(_resolve_name(arg.annotation))
        default = None
        optional = False
        if i < len(kw_defaults) and kw_defaults[i] is not None:
            try:
                default = ast.literal_eval(kw_defaults[i])
            except Exception:
                default = None
            optional = True
        params.append(Param(name=arg.arg, type=param_type, optional=optional, default=default))
    # **kwargs
    if func.args.kwarg:
        k = func.args.kwarg
        ktype = _map_type(_resolve_name(k.annotation)) if k.annotation else "any"
        params.append(Param(name=k.arg, type=f"Record<string, {ktype}>", optional=True, default=None))

    returns = "None"
    if func.returns:
        returns = _map_type(_resolve_name(func.returns))

    docstring = ast.get_docstring(func) or ""

    return Method(
        name=func.name,
        type=method_type,
        payable=payable,
        params=params,
        returns=returns,
        docstring=docstring,
    )


def _find_contract_class(node: ast.AST) -> ast.ClassDef | None:
    """Find the first Contract class in source order (depth-first)."""
    if isinstance(node, ast.ClassDef) and _is_contract_class(node):
        return node
    for child in ast.iter_child_nodes(node):
        result = _find_contract_class(child)
        if result is not None:
            return result
    return None


@functools.lru_cache(maxsize=128)
def extract_abi(source_code: str) -> ContractAbi:
    """Extract ABI from GenLayer Intelligent Contract Python source."""
    tree = ast.parse(source_code)

    contract_node = _find_contract_class(tree)
    if contract_node is not None:
        contract_name = contract_node.name
        methods: list[Method] = []
        for item in contract_node.body:
            if isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef)):
                method = _parse_method(item)
                if method:
                    methods.append(method)
        return ContractAbi(contract_name=contract_name, methods=methods)

    # Fallback: if no Contract class found, look for top-level functions with decorators
    methods: list[Method] = []
    for node in tree.body:
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            method = _parse_method(node)
            if method:
                methods.append(method)
    if methods:
        # Try to infer contract name from class definitions
        for n in ast.walk(tree):
            if isinstance(n, ast.ClassDef):
                return ContractAbi(contract_name=n.name, methods=methods)
        return ContractAbi(contract_name="UnknownContract", methods=methods)

    raise ValueError("No GenLayer contract class or public methods found in source code.")


def abi_to_dict(abi: ContractAbi) -> dict[str, Any]:
    """Serialize ContractAbi to a plain dict."""
    return {
        "contract_name": abi.contract_name,
        "methods": [
            {
                "name": m.name,
                "type": m.type,
                "payable": m.payable,
                "params": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "optional": p.optional,
                        "default": p.default,
                    }
                    for p in m.params
                ],
                "returns": m.returns,
                "docstring": m.docstring,
            }
            for m in abi.methods
        ],
    }
