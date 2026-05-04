"""TypeScript ABI and React hooks generators."""

import json
from .parser import ContractAbi, Method, Param


def _extract_generics(gl_type: str) -> tuple[str, str]:
    """Extract base type and generic content, matching nested angle brackets."""
    if "<" not in gl_type:
        return gl_type, ""
    first_lt = gl_type.index("<")
    base = gl_type[:first_lt].strip()
    depth = 1
    i = first_lt + 1
    while i < len(gl_type) and depth > 0:
        if gl_type[i] == "<":
            depth += 1
        elif gl_type[i] == ">":
            depth -= 1
        i += 1
    if depth != 0:
        generics = gl_type[first_lt + 1 :]
    else:
        generics = gl_type[first_lt + 1 : i - 1]
    return base, generics


def _split_generics(generics: str) -> list[str]:
    """Split generic arguments by comma at top-level depth only."""
    parts: list[str] = []
    current = ""
    depth = 0
    for char in generics:
        if char == "<":
            depth += 1
            current += char
        elif char == ">":
            depth -= 1
            current += char
        elif char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        parts.append(current.strip())
    return parts


def _ts_type(gl_type: str) -> str:
    """Map GenLayer types to TypeScript types."""
    mapping = {
        "str": "string",
        "u256": "bigint | number | string",
        "int": "bigint | number | string",
        "bool": "boolean",
        "f64": "number",
        "bytes": "string",
        "dict": "Record<string, any>",
        "DynArray": "__DYNARRAY__",
        "list": "any[]",
        "tuple": "[any, ...any[]]",
        "Address": "string",
        "None": "null",
        "any": "any",
    }
    # Handle union types at top level
    if " | " in gl_type:
        return " | ".join(_ts_type(part.strip()) for part in gl_type.split(" | "))
    base, generics = _extract_generics(gl_type)
    mapped = mapping.get(base, base)
    if generics:
        inner = ", ".join(_ts_type(g) for g in _split_generics(generics))
        if mapped == "__DYNARRAY__":
            return f"{inner}[]"
        return f"{mapped}<{inner}>"
    if mapped == "__DYNARRAY__":
        return "any[]"
    return mapped


def _ts_return_type(gl_type: str) -> str:
    """Map return type: standalone None becomes void, unions keep null."""
    mapped = _ts_type(gl_type)
    return "void" if mapped == "null" and " | " not in gl_type else mapped


def generate_ts_abi(abi: ContractAbi, contract_address: str = "0x0000...") -> str:
    """Generate TypeScript ABI object as code string."""
    lines: list[str] = [
        f"// Auto-generated from contract at {contract_address}",
        f"export const {abi.contract_name}Abi = {{",
        f'  address: "{contract_address}" as const,',
        "  methods: {",
    ]
    for m in abi.methods:
        params_str = ", ".join(f'"{p.name}"' for p in m.params)
        returns_str = json.dumps(m.returns)
        lines.append(f"    {m.name}: {{")
        lines.append(f'      type: "{m.type}" as const,')
        if m.payable:
            lines.append("      payable: true as const,")
        lines.append(f"      params: [{params_str}] as const,")
        lines.append(f"      returns: {returns_str} as const,")
        lines.append("    },")
    lines.append("  },")
    lines.append("} as const;")
    lines.append("")

    # Generate typed method names
    lines.append(f"export type {abi.contract_name}MethodName = keyof typeof {abi.contract_name}Abi.methods;")
    lines.append("")

    # Generate parameter types
    for m in abi.methods:
        if m.params:
            params_type = "; ".join(f"{p.name}: {_ts_type(p.type)}" for p in m.params)
            lines.append(f"export type {abi.contract_name}_{m.name}_Params = {{ {params_type} }};")
        else:
            lines.append(f"export type {abi.contract_name}_{m.name}_Params = {{}};")
    lines.append("")

    # Generate return types
    for m in abi.methods:
        lines.append(f"export type {abi.contract_name}_{m.name}_Returns = {_ts_return_type(m.returns)};")
    lines.append("")

    return "\n".join(lines)


def _to_pascal_case(snake: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in snake.split("_"))


def _generate_hook_for_method(
    contract_name: str, method: Method, use_import: str = "genlayer-js/hooks"
) -> str:
    """Generate React hook for a single method."""
    hook_name = f"use{contract_name}{_to_pascal_case(method.name)}"
    params_type = f"{contract_name}_{method.name}_Params"
    returns_type = f"{contract_name}_{method.name}_Returns"

    if method.type == "view":
        code = f"""\
export function {hook_name}(client: any, params: {params_type}) {{
  return useContractRead<{returns_type}>(client, {contract_name}Abi.address, "{method.name}", params);
}}
"""
    elif method.payable:
        code = f"""\
export function {hook_name}(
  client: any,
  params: {params_type},
  value: bigint | number | string
) {{
  return useContractWritePayable<{returns_type}>(
    client,
    {contract_name}Abi.address,
    "{method.name}",
    params,
    value
  );
}}
"""
    else:
        code = f"""\
export function {hook_name}(client: any, params: {params_type}) {{
  return useContractWrite<{returns_type}>(client, {contract_name}Abi.address, "{method.name}", params);
}}
"""
    return code


def generate_react_hooks(abi: ContractAbi) -> str:
    """Generate React hooks file content."""
    if not abi.methods:
        return f'import {{ useContractRead, useContractWrite, useContractWritePayable }} from "genlayer-js/hooks";\n'

    lines: list[str] = [
        f'import {{ useContractRead, useContractWrite, useContractWritePayable }} from "genlayer-js/hooks";',
    ]

    # Collect all types to import
    param_types = [f"{abi.contract_name}_{m.name}_Params" for m in abi.methods]
    return_types = [f"{abi.contract_name}_{m.name}_Returns" for m in abi.methods]
    all_types = [abi.contract_name + "Abi"] + param_types + return_types
    lines.append(
        f'import {{ {", ".join(all_types)} }} from "./{abi.contract_name}Abi";'
    )
    lines.append("")

    for m in abi.methods:
        lines.append(_generate_hook_for_method(abi.contract_name, m))

    return "\n".join(lines)


def generate_full_ts_package(abi: ContractAbi, contract_address: str = "0x0000...") -> dict[str, str]:
    """Generate all TypeScript files for a contract."""
    return {
        f"{abi.contract_name}Abi.ts": generate_ts_abi(abi, contract_address),
        f"{abi.contract_name}Hooks.ts": generate_react_hooks(abi),
    }


def generate_genlayer_js_wrapper(
    abi: ContractAbi,
    contract_address: str = "0x0000...",
    rpc_url: str = "https://zksync-os-testnet-genlayer.zksync.dev",
    chain_id: int = 4221,
) -> str:
    """Generate genlayer-js wrapper functions."""
    type_imports: list[str] = [f"{abi.contract_name}Abi"]
    for m in abi.methods:
        type_imports.append(f"{abi.contract_name}_{m.name}_Params")
        type_imports.append(f"{abi.contract_name}_{m.name}_Returns")

    lines: list[str] = [
        f'import {{ createClient }} from "genlayer-js";',
        f'import {{ {", ".join(type_imports)} }} from "./{abi.contract_name}Abi";',
        "",
        f"const client = createClient({{ chain: {{ rpc: '{rpc_url}', chainId: {chain_id} }} }});",
        "",
        f"export const contractAddress = '{contract_address}' as const;",
        "",
    ]

    for m in abi.methods:
        params_type = f"{abi.contract_name}_{m.name}_Params"
        returns_type = f"{abi.contract_name}_{m.name}_Returns"
        args = ", ".join(p.name for p in m.params)
        param_destructure = "{ " + ", ".join(p.name for p in m.params) + " }" if m.params else "{}"

        if m.type == "view":
            lines.append(f"""\
export async function {m.name}({param_destructure}: {params_type}): Promise<{returns_type}> {{
  return client.readContract({{
    address: contractAddress,
    functionName: "{m.name}",
    args: [{args}],
  }});
}}
""")
        elif m.payable:
            lines.append(f"""\
export async function {m.name}(
  {param_destructure}: {params_type},
  value: bigint | number | string
): Promise<{returns_type}> {{
  return client.writeContract({{
    address: contractAddress,
    functionName: "{m.name}",
    args: [{args}],
    value,
  }});
}}
""")
        else:
            lines.append(f"""\
export async function {m.name}({param_destructure}: {params_type}): Promise<{returns_type}> {{
  return client.writeContract({{
    address: contractAddress,
    functionName: "{m.name}",
    args: [{args}],
  }});
}}
""")

    return "\n".join(lines)
