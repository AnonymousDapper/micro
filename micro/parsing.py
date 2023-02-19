# The MIT License (MIT)

# Copyright (c) 2022 AnonymousDapper

__all__ = ()

import ast
import tokenize
from io import BytesIO
from pathlib import Path
from typing import Callable, Iterator, Union

from micro import consts, logger

log = logger.get_logger(__name__)


def as_line_iter(src: Union[str, bytes, Path]) -> Callable[..., bytes]:
    if isinstance(src, Path):
        return BytesIO(src.read_bytes()).readline

    elif isinstance(src, str):
        return BytesIO(src.encode("utf-8")).readline

    return BytesIO(src).readline


def fix_tokens(src: Callable[..., bytes]) -> Iterator[tuple[int, str]]:
    prev_ident = None
    in_substitute = False

    for token, text, _, _, _ in tokenize.tokenize(src):
        match (token, text):
            case (tokenize.NAME, _):
                # handle `ident !`
                #         ^^^^^
                if prev_ident is not None:
                    yield tokenize.NAME, prev_ident

                # handle `? ident`
                #           ^^^^
                elif in_substitute:
                    yield tokenize.NAME, consts.MACRO_SAFE_SUBST + text
                    in_substitute = False
                    continue

                    # continuing here prevents us from accepting something like `? ident !`

                prev_ident = text

            # handle `ident !`
            #               ^
            case (tokenize.ERRORTOKEN, consts.MACRO_CALL):
                if prev_ident is not None:
                    yield tokenize.NAME, (prev_ident + consts.MACRO_SAFE_CALL)
                    prev_ident = None
                    continue

                yield token, text

            # handle `? ident`
            #         ^
            case (tokenize.ERRORTOKEN, consts.MACRO_SUBST):
                if not in_substitute:
                    in_substitute = True

                # otherwise just propagate the inevitable syntax error

            case _:
                if prev_ident is not None:
                    yield tokenize.NAME, prev_ident
                    prev_ident = None

                yield token, text


def parse_rename_safe(source: Union[str, Path]) -> ast.AST:
    file = Path(source)
    new_source = tokenize.untokenize(fix_tokens(as_line_iter(file))).decode()
    # log.debug(f"::: Source {file.name}\n{new_source}\n:::")
    tree = ast.parse(new_source, file.name, "exec", **consts.AST_OPTS)

    renamed = ast.fix_missing_locations(MacroRewriter().visit(tree))

    return renamed


class MacroRewriter(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name):
        if node.id.endswith(consts.MACRO_SAFE_CALL):
            node.id = node.id[: -consts.MACRO_SAFE_CALL_LEN] + consts.MACRO_CALL

        elif node.id.startswith(consts.MACRO_SAFE_SUBST):
            node.id = consts.MACRO_SUBST + node.id[consts.MACRO_SAFE_SUBST_LEN :]

        # elif node.id == consts.MACRO_SAFE_QUOTE:
        #     node.id = consts.MACRO_QUOTE

        return node

    def visit_Attribute(self, node: ast.Attribute):
        self.generic_visit(node)

        if node.attr.startswith(consts.MACRO_SAFE_SUBST):
            node.attr = consts.MACRO_SUBST + node.attr[consts.MACRO_SAFE_SUBST_LEN :]

        return node

    def visit_keyword(self, node: ast.keyword):
        if node.arg.startswith(consts.MACRO_SAFE_SUBST):
            node.arg = consts.MACRO_SUBST + node.arg[consts.MACRO_SAFE_SUBST_LEN :]

        return node

    def visit_ClassDef(self, node: ast.ClassDef):
        self.generic_visit(node)

        if node.name.startswith(consts.MACRO_SAFE_SUBST):
            node.name = consts.MACRO_SUBST + node.name[consts.MACRO_SAFE_SUBST_LEN :]

        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.generic_visit(node)

        if node.name.startswith(consts.MACRO_SAFE_SUBST):
            node.name = consts.MACRO_SUBST + node.name[consts.MACRO_SAFE_SUBST_LEN :]

        return node
