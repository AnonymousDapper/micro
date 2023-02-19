# The MIT License (MIT)

# Copyright (c) 2022 AnonymousDapper

__all__ = ()

import ast
import sys
from importlib.machinery import ModuleSpec, PathFinder
from pathlib import Path
from types import ModuleType

import astpretty

from micro import cleanup, logger, parsing, tree

log = logger.get_logger(__name__)


class MacroImporter:
    @classmethod
    def find_spec(cls, fullname: str, path, target=None):
        source_spec = PathFinder.find_spec(fullname, path, target)

        if source_spec is not None:
            source_spec.loader = cls()  # type: ignore

            return source_spec

    def create_module(self, _: ModuleSpec):
        ...

    def exec_module(self, module: ModuleType):
        if module.__file__ is None:
            raise ValueError(f"Module {module} has no __file__")

        file_path = Path(module.__file__)
        source_tree = parsing.parse_rename_safe(file_path)

        #log.info(f"[[ Original AST {file_path.name}\n{astpretty.pformat(source_tree, show_offsets=False)}\n]]")

        #log.debug(f"<< Prepared source: {file_path.name}\n{ast.unparse(source_tree)}\n>>")

        transformed_tree = tree.MacroTransformer(file_path.name, module.__name__).visit(source_tree)

        cleaned_tree = ast.fix_missing_locations(
            cleanup.CleanupTransformer(file_path.name, module.__name__).visit(transformed_tree)
        )

        #log.info(f"# [[ Transformed AST {file_path.name}\n{astpretty.pformat(cleaned_tree, show_offsets=False)}\n]]")

        #log.debug(f"<< Transformed source: {file_path.name}\n{ast.unparse(cleaned_tree)}\n>>")

        code = compile(cleaned_tree, file_path.name, "exec")
        exec(code, module.__dict__, module.__dict__)


sys.meta_path.insert(0, MacroImporter)
