# The MIT License (MIT)

# Copyright (c) 2022 AnonymousDapper

from __future__ import annotations

__all__ = ("Symbol", "SymbolRef", "Namespace", "SymbolTree", "MacroContext")

from dataclasses import dataclass
from importlib._bootstrap import _gcd_import
from typing import TYPE_CHECKING, Any, Callable, Iterator, Optional, Union, cast

import prettyformatter

from micro import logger

if TYPE_CHECKING:
    from ast import FunctionDef
    from types import ModuleType

log = logger.get_logger(__name__)

ProcMacro = Callable[["MacroContext", "FunctionDef"], Any]
NamedItem = Union["Namespace", "SymbolRef"]


@dataclass
class MacroContext:
    file: str
    path: list[str]


@dataclass
class Symbol:
    name: str

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return f"<{self.name}>"


class SymbolRef:
    def __init__(self, parents: list[Symbol], symbol: Symbol):
        self.path = parents
        self.symbol = symbol

    @classmethod
    def from_str(cls, path: str):
        parent, _, sym = path.rpartition(".")
        parents = parent.split(".") if parent else []

        return cls([Symbol(p) for p in parents], Symbol(sym))

    def parent(self):
        if len(self.path) > 0:
            pcount = len(self.path)
            return SymbolRef(self.path[: pcount - 1], self.path[pcount - 1])

    def chain(self, new: Symbol) -> SymbolRef:
        parts = [*self.path, self.symbol]

        return self.__class__(parts, new)

    def __hash__(self):
        return sum(hash(p) for p in self.path) + hash(self.symbol)

    def __eq__(self, other):
        if isinstance(other, SymbolRef):
            return self.path == other.path and self.symbol == other.symbol

    def __str__(self):
        return f"{'.'.join(symbol.name for symbol in self.path)}{'.' if len(self.path) else ''}{self.symbol.name}"

    def __repr__(self):
        path = ".".join(repr(p) for p in self.path)
        return f"@{path}.{self.symbol}"


class Namespace:
    def __init__(self, name: Symbol):
        self.name = name
        self.namespace: dict[Symbol, NamedItem] = {}

    def add_item(self, name: Symbol, value: NamedItem, *, warn_on_overwrite=True):
        # log.warn(f"AddItem {self.name} -> {name} {value}")
        if name in self.namespace and warn_on_overwrite:
            log.warn(f"Item `{name}` already exists in namespace `{self.name}` as {self.namespace[name]}")

        self.namespace[name] = value

    def add_namespace(self, namespace: "Namespace"):
        self.add_item(namespace.name, namespace)

        return namespace

    def ensure_exists(self, ref: SymbolRef):
        namespace = self
        for symbol in ref.path:
            # log.debug(f"Ensure:: {namespace.name} -> {symbol} [{namespace!r}]")
            if symbol not in namespace:
                namespace = namespace.add_namespace(Namespace(symbol))
            else:
                if isinstance(namespace[symbol], Namespace):
                    namespace = cast(Namespace, namespace[symbol])

        if ref.symbol not in namespace:
            # log.debug(f"Ensure:: {namespace.name} -> {ref.symbol} [{namespace!r}] !")
            namespace.add_namespace(Namespace(ref.symbol))

    def resolve_ref(self, ref: SymbolRef) -> "Namespace":
        namespace = self
        for part in ref.path:
            if part in namespace:
                item = namespace[part]
                # log.debug(f"Resolve :: {namespace.name} ({ref}) : {part} -> {item}")

                if isinstance(item, Namespace):
                    namespace = item

                else:
                    namespace = self.resolve_ref(item)

            else:
                raise KeyError(f"symbol {part} not in {namespace!s}")

        if ref.symbol in namespace:
            item = namespace[ref.symbol]
            # log.debug(f"Resolve :: {namespace.name} ({ref}) : {ref.symbol} -> {item} !")

            if isinstance(item, SymbolRef):
                item = self.resolve_ref(item)

            return item

        raise KeyError(f"symbol {ref.symbol} not in {namespace!s}")

    def lookup_ref(self, ref: SymbolRef) -> Optional[SymbolRef]:
        namespace = self
        for part in ref.path:
            if part in namespace:
                item = namespace[part]

                if isinstance(item, Namespace):
                    namespace = item

                else:
                    break

        if ref.symbol in namespace:
            item = namespace[ref.symbol]

            if isinstance(item, SymbolRef):
                return item

            elif isinstance(item, Namespace):
                return ref

    def __iter__(self) -> Iterator[tuple[Symbol, NamedItem]]:
        for k, v in self.namespace.items():
            yield k, v

    def __contains__(self, key: Symbol) -> bool:
        if isinstance(key, Symbol):
            return key in self.namespace.keys()

        return False

    def __getitem__(self, key: Symbol) -> NamedItem:
        if isinstance(key, Symbol):
            if key in self.namespace.keys():
                return self.namespace[key]

            raise KeyError(key)

        raise TypeError(type(key))

    def __str__(self):
        return f"Namespace[{self.name}]"

    def __repr__(self):
        return f"{prettyformatter.pformat(self.namespace, indent=4)}"


class SymbolTreeBuilder:
    def __init__(self):
        self.namespace = Namespace(Symbol(""))

        self.module_cache: dict[SymbolRef, "ModuleType"] = {}
        self.macro_cache: dict[SymbolRef, "FunctionDef"] = {}
        self.proc_macro_cache: dict[SymbolRef, ProcMacro] = {}

    def _get_ref(self, path: list[str], item: str) -> SymbolRef:
        parts = [Symbol(p) for p in path]
        return SymbolRef(parts, Symbol(item))

    def add_item(self, ref: SymbolRef, item: NamedItem, **kwargs):
        if parent := ref.parent():
            namespace = self.namespace.resolve_ref(parent)
            namespace.add_item(ref.symbol, item, **kwargs)

        else:
            self.namespace.add_item(ref.symbol, item, **kwargs)

    # def remove_item(self, ref: SymbolRef, item: NamedItem):
    #     if parent := ref.parent():
    #         namespace = self.namespace.resolve_ref(parent)
    #         namespace.remove_item(ref.symbol, item)

    #     else:
    #         self.namespace.remove_item(ref.symbol, item)

    def register_macro(self, path: list[str], name: str, node: "FunctionDef"):
        ref = self._get_ref(path, name)
        self.namespace.ensure_exists(ref)
        self.add_item(ref, Namespace(ref.symbol), warn_on_overwrite=False)

        if ref in self.macro_cache:
            log.warn(f"Macro {ref} already exists")

        self.macro_cache[ref] = node

    def register_proc_macro(self, path: str, name: str, fn: ProcMacro):
        ref = self._get_ref(path.split(), name)
        self.namespace.ensure_exists(ref)

        self.add_item(ref, Namespace(ref.symbol), warn_on_overwrite=False)

        # log.debug(f"Ref: {ref!r}")

        if ref in self.proc_macro_cache:
            log.warn(f"Macro {ref} already exists")

        self.proc_macro_cache[ref] = fn

    def check_macro(self, path: list[str], name: str):
        ref = self._get_ref(path, name)

        if (result := self.namespace.lookup_ref(ref)) is not None:
            if result in self.macro_cache.keys() or result in self.proc_macro_cache.keys():
                return True

        return False

    def lookup_macro(self, path: list[str], name: str):
        ref = self._get_ref(path, name)

        # log.debug(f"Ref: {ref!r}")
        # log.debug(f"Namespace: {self.namespace!r}")

        if (result := self.namespace.lookup_ref(ref)) is None:
            raise NameError(f"{ref} does not exist")

        if result in self.macro_cache.keys():
            return self.macro_cache[result]

    def lookup_proc_macro(self, path: list[str], name: str):
        ref = self._get_ref(path, name)

        if (result := self.namespace.lookup_ref(ref)) is None:
            raise NameError(f"{ref} does not exist")

        if result in self.proc_macro_cache.keys():
            return self.proc_macro_cache[result]

        # raise NameError(f"{result} not registered")

    def add_import(
        self,
        path: list[str],
        module: str,
        *,
        import_from: Optional[str] = None,
        asname: Optional[str] = None,
        package: Optional[str] = None,
        level: int = 0,
    ):
        name = asname or import_from or module
        # log.debug(f":: Import {f'{import_from} from {module}' if import_from else module}{f' as {name}' if asname else ''} ({package}) | {path}")

        module_ref = SymbolRef.from_str(module)

        tmp: list[Symbol] = []
        for section in module_ref.path:
            mod_ref = SymbolRef(tmp, section)

            self.__import(mod_ref, package, level)
            tmp.append(section)

        del tmp
        self.__import(module_ref, package, level)

        parts = [Symbol(p) for p in path]
        ref = SymbolRef(parts[:-1], parts[-1])

        self.namespace.ensure_exists(ref)
        namespace = self.namespace.resolve_ref(ref)

        import_ref = module_ref.chain(Symbol(import_from or module))

        namespace.add_item(Symbol(name), import_ref)

        # log.debug(f"++ Setting up {ref.chain(Symbol(name)).tostring()} to provide {import_ref.tostring()}")
        # log.debug(f"Module: {module_ref}")

        # log.debug(f"Path: {ref}")

        # log.debug(f"Namespace: {namespace}{namespace!r}")
        # log.debug(f"Root Namespace: {self.namespace!r}")

    def __import(self, ref: SymbolRef, package: Optional[str] = None, level: int = 2):
        if not ref in self.module_cache:
            # log.debug(f"-- Importing {ref} to {ref.tostring()}")
            self.module_cache[ref] = _gcd_import(str(ref), package, level)
        # else:
        # log.debug(f"-- Import cached {ref} to {ref.tostring()}")


SymbolTree = SymbolTreeBuilder()
