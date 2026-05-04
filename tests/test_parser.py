"""Unit tests for GenLayer ABI Generator parser and generator."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from genlayer_abi.parser import extract_abi, abi_to_dict
from genlayer_abi.generator import generate_ts_abi, generate_react_hooks, generate_genlayer_js_wrapper


class TestParser(unittest.TestCase):
    def test_simple_view(self):
        source = """
import genlayer.py._native as gl

class MyContract(gl.Contract):
    @gl.public.view
    def get_value(self) -> str:
        return "hello"
"""
        abi = extract_abi(source)
        self.assertEqual(abi.contract_name, "MyContract")
        self.assertEqual(len(abi.methods), 1)
        self.assertEqual(abi.methods[0].name, "get_value")
        self.assertEqual(abi.methods[0].type, "view")
        self.assertEqual(abi.methods[0].returns, "str")

    def test_write_with_params(self):
        source = """
import genlayer.py._native as gl
from genlayer.py.types import u256, Address

class Token(gl.Contract):
    @gl.public.write
    def transfer(self, to: Address, amount: u256) -> bool:
        return True
"""
        abi = extract_abi(source)
        self.assertEqual(abi.contract_name, "Token")
        self.assertEqual(len(abi.methods), 1)
        m = abi.methods[0]
        self.assertEqual(m.name, "transfer")
        self.assertEqual(m.type, "write")
        self.assertFalse(m.payable)
        self.assertEqual(len(m.params), 2)
        self.assertEqual(m.params[0].name, "to")
        self.assertEqual(m.params[0].type, "Address")
        self.assertEqual(m.params[1].name, "amount")
        self.assertEqual(m.params[1].type, "u256")

    def test_payable(self):
        source = """
import genlayer.py._native as gl
from genlayer.py.types import u256

class Auction(gl.Contract):
    @gl.public.write.payable
    def bid(self, amount: u256) -> bool:
        return True
"""
        abi = extract_abi(source)
        m = abi.methods[0]
        self.assertEqual(m.type, "write")
        self.assertTrue(m.payable)

    def test_optional_params(self):
        source = """
import genlayer.py._native as gl

class Config(gl.Contract):
    @gl.public.write
    def set(self, key: str, value: str = "default") -> None:
        pass
"""
        abi = extract_abi(source)
        m = abi.methods[0]
        self.assertEqual(len(m.params), 2)
        self.assertFalse(m.params[0].optional)
        self.assertTrue(m.params[1].optional)
        self.assertEqual(m.params[1].default, "default")

    def test_generic_types(self):
        source = """
import genlayer.py._native as gl
from genlayer.py.types import DynArray, TreeMap, u256

class Data(gl.Contract):
    @gl.public.view
    def list_items(self) -> DynArray[dict]:
        return []

    @gl.public.view
    def map_scores(self) -> TreeMap[u256, str]:
        return {}
"""
        abi = extract_abi(source)
        self.assertEqual(len(abi.methods), 2)
        self.assertEqual(abi.methods[0].returns, "DynArray<dict>")
        self.assertEqual(abi.methods[1].returns, "TreeMap<u256, str>")

    def test_abi_to_dict(self):
        source = """
import genlayer.py._native as gl

class X(gl.Contract):
    @gl.public.view
    def f(self) -> str:
        return "x"
"""
        abi = extract_abi(source)
        d = abi_to_dict(abi)
        self.assertEqual(d["contract_name"], "X")
        self.assertIn("methods", d)

    def test_no_contract_fallback(self):
        source = """
import genlayer.py._native as gl

@gl.public.view
def standalone() -> str:
    return "ok"
"""
        abi = extract_abi(source)
        self.assertEqual(len(abi.methods), 1)
        self.assertEqual(abi.methods[0].name, "standalone")


class TestParserEdgeCases(unittest.TestCase):
    def test_nested_generics(self):
        source = """
import genlayer.py._native as gl
from genlayer.py.types import u256, DynArray, TreeMap

class Nested(gl.Contract):
    @gl.public.view
    def matrix(self) -> DynArray[DynArray[u256]]:
        return []

    @gl.public.view
    def tree(self) -> TreeMap[u256, DynArray[str]]:
        return {}
"""
        abi = extract_abi(source)
        self.assertEqual(abi.contract_name, "Nested")
        self.assertEqual(len(abi.methods), 2)
        self.assertEqual(abi.methods[0].returns, "DynArray<DynArray<u256>>")
        self.assertEqual(abi.methods[1].returns, "TreeMap<u256, DynArray<str>>")

    def test_decorator_with_parens(self):
        source = """
import genlayer.py._native as gl
from genlayer.py.types import u256

class Parens(gl.Contract):
    @gl.public.write.payable()
    def bid(self, amount: u256) -> bool:
        return True
"""
        abi = extract_abi(source)
        self.assertEqual(len(abi.methods), 1)
        m = abi.methods[0]
        self.assertEqual(m.name, "bid")
        self.assertEqual(m.type, "write")
        self.assertTrue(m.payable)

    def test_full_module_path_contract(self):
        source = """
import genlayer.py._native as gl
from genlayer.py.types import u256

class FullPath(gl.Contract):
    @gl.public.view
    def get(self) -> u256:
        return 0
"""
        abi = extract_abi(source)
        self.assertEqual(abi.contract_name, "FullPath")
        self.assertEqual(len(abi.methods), 1)

    def test_union_types(self):
        source = """
import genlayer.py._native as gl

class UnionTest(gl.Contract):
    @gl.public.view
    def maybe_get(self, key: str) -> str | None:
        return None
"""
        abi = extract_abi(source)
        m = abi.methods[0]
        self.assertEqual(m.returns, "str | None")

    def test_kwonlyargs_and_varargs(self):
        source = """
import genlayer.py._native as gl
from genlayer.py.types import u256

class Params(gl.Contract):
    @gl.public.write
    def advanced(self, a: u256, *args: str, b: str = "default", **kwargs: u256) -> None:
        pass
"""
        abi = extract_abi(source)
        m = abi.methods[0]
        names = [p.name for p in m.params]
        self.assertIn("a", names)
        self.assertIn("args", names)
        self.assertIn("b", names)
        self.assertIn("kwargs", names)

    def test_multiple_contracts_first_wins(self):
        source = """
import genlayer.py._native as gl
from genlayer.py.types import u256

class First(gl.Contract):
    @gl.public.view
    def one(self) -> u256:
        return 1

class Second(gl.Contract):
    @gl.public.view
    def two(self) -> u256:
        return 2
"""
        abi = extract_abi(source)
        self.assertEqual(abi.contract_name, "First")
        self.assertEqual(len(abi.methods), 1)
        self.assertEqual(abi.methods[0].name, "one")


class TestGenerator(unittest.TestCase):
    def test_ts_abi_output(self):
        source = """
import genlayer.py._native as gl
from genlayer.py.types import u256

class Counter(gl.Contract):
    @gl.public.view
    def get_count(self) -> u256:
        return 0
"""
        abi = extract_abi(source)
        ts = generate_ts_abi(abi, "0x1234")
        self.assertIn("export const CounterAbi", ts)
        self.assertIn("address: \"0x1234\" as const", ts)
        self.assertIn("get_count", ts)
        self.assertIn("type: \"view\" as const", ts)

    def test_hooks_output(self):
        source = """
import genlayer.py._native as gl
from genlayer.py.types import u256

class Counter(gl.Contract):
    @gl.public.view
    def get_count(self) -> u256:
        return 0
"""
        abi = extract_abi(source)
        hooks = generate_react_hooks(abi)
        self.assertIn("useCounterGetCount", hooks)
        self.assertIn("useContractRead", hooks)

    def test_wrapper_output(self):
        source = """
import genlayer.py._native as gl
from genlayer.py.types import u256

class Counter(gl.Contract):
    @gl.public.write
    def increment(self, by: u256) -> u256:
        return 0
"""
        abi = extract_abi(source)
        wrapper = generate_genlayer_js_wrapper(abi, "0x1234")
        self.assertIn("createClient", wrapper)
        self.assertIn("client.writeContract", wrapper)
        self.assertIn("increment", wrapper)

    def test_nested_generics_ts(self):
        source = """
import genlayer.py._native as gl
from genlayer.py.types import u256, DynArray, TreeMap

class Nested(gl.Contract):
    @gl.public.view
    def matrix(self) -> DynArray[DynArray[u256]]:
        return []
"""
        abi = extract_abi(source)
        ts = generate_ts_abi(abi)
        self.assertIn("DynArray<DynArray<u256>>", ts)

    def test_union_type_ts(self):
        source = """
import genlayer.py._native as gl

class UnionTest(gl.Contract):
    @gl.public.view
    def maybe_get(self, key: str) -> str | None:
        return None
"""
        abi = extract_abi(source)
        ts = generate_ts_abi(abi)
        self.assertIn("string | null", ts)


if __name__ == "__main__":
    unittest.main()
