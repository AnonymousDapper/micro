# The MIT License (MIT)

# Copyright (c) 2022 AnonymousDapper

__all__ = ("MacroTransformer",)

import ast

from micro import consts, logger, walker
from micro.symbol import MacroContext, SymbolTree

log = logger.get_logger(__name__)


class MacroTransformer(ast.NodeTransformer):
    def __init__(self, file: str, module: str):
        self.filename = file
        self.path = module.split(".")

        self.found_macro = False

        super().__init__()

    def __build_context(self) -> MacroContext:
        return MacroContext(self.filename, self.path)

    def visit_Import(self, node: ast.Import):
        # log.debug(f":: Import: {astpretty.pformat(node, show_offsets=False)}")
        for name in node.names:
            SymbolTree.add_import(self.path, name.name, asname=name.asname)

        return node

    def visit_ImportFrom(self, node: ast.ImportFrom):
        # log.debug(f":: ImportFrom: {astpretty.pformat(node, show_offsets=False)}")
        for name in node.names:
            SymbolTree.add_import(
                self.path,
                node.module or "",
                import_from=name.name,
                asname=name.asname,
                package=".".join(self.path),
                level=node.level,
            )

        return node

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)

        match node.func:
            case ast.Name(id=name) if name.endswith(consts.MACRO_CALL):
                # handle quote in cleanup

                if name == consts.MACRO_QUOTE:
                    return node

                self.found_macro = True
                name = name[: -consts.MACRO_CALL_LEN]

                log.info(f"! Invoke [call] of `{name}` at {'.'.join(self.path)} ")

                if macro := SymbolTree.lookup_macro(self.path, name):

                    node = walker.call_invoke(node, macro)

                else:
                    log.error(f"Error on call invoke `{name}`: macro not found")

        return node

    def visit_Subscript(self, node: ast.Subscript):
        self.generic_visit(node)

        match node.value:
            case ast.Name(id=name) if name.endswith(consts.MACRO_CALL):
                self.found_macro = True
                name = name[: -consts.MACRO_CALL_LEN]

                log.info(f"! Invoke [subscript] of `{name}` at {'.'.join(self.path)}")

                if macro := SymbolTree.lookup_macro(self.path, name):

                    node = walker.subscript_invoke(node, macro)

                else:
                    log.error(f"Error on subscript invoke `{name}`: macro not found")

        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.path.append(node.name)
        self.generic_visit(node)
        self.path.pop()

        for decorator in node.decorator_list:
            match decorator:
                case ast.Name(id=name) if name.endswith(consts.MACRO_CALL):
                    self.found_macro = True
                    name = name[: -consts.MACRO_CALL_LEN]

                    log.info(f"! Invoke [decorator] of `{name}` at {'.'.join(self.path)}")

                    if macro := SymbolTree.lookup_proc_macro(self.path, name):

                        node = macro(self.__build_context(), node)

                    else:
                        log.error(f"Error on decorator invoke `{name}`: macro not found")

        return node

    def visit_Expr(self, node: ast.Expr):
        match node.value:
            case ast.Call():
                tree = self.visit_Call(node.value)
                if self.found_macro:
                    self.found_macro = False
                    return tree

            case ast.Subscript():
                tree = self.visit_Subscript(node.value)
                if self.found_macro:
                    self.found_macro = False
                    return tree

            case ast.FunctionDef():
                tree = self.visit_FunctionDef(node.value)
                if self.found_macro:
                    self.found_macro = False
                    return tree

            case _:
                self.generic_visit(node)

        return node
