# The MIT License (MIT)

# Copyright (c) 2022 AnonymousDapper

__all__ = ()

import ast

from micro import consts, logger
from micro.symbol import SymbolTree

log = logger.get_logger(__name__)


class CleanupTransformer(ast.NodeTransformer):
    def __init__(self, file: str, module: str):
        self.filename = file
        self.path = module.split(".")

        super().__init__()

    def visit_Assign(self, node: ast.Assign):
        self.generic_visit(node)

        for idx, target in enumerate(node.targets):
            match target:
                case ast.Name(ctx=ast.Load()):
                    node.targets[idx].ctx = ast.Store()  # type: ignore

        return node

    def visit_Import(self, node: ast.Import):
        for idx, name in enumerate(node.names):
            if SymbolTree.check_macro(self.path, name.name):
                del node.names[idx]

        if len(node.names) > 0:
            return node

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for idx, name in enumerate(node.names):
            if SymbolTree.check_macro(self.path, name.name):
                del node.names[idx]

        if len(node.names) > 0:
            return node

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)

        match node.func:
            case ast.Name(id=name) if name == consts.MACRO_QUOTE:
                # log.debug(f"! Invoke [call] of `quote` at {'.'.join(self.path)}")

                return ast.Constant(value=ast.unparse(node)[consts.MACRO_QUOTE_LEN + 1 : -1])

        return node
