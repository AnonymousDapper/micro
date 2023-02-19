# The MIT License (MIT)

# Copyright (c) 2022 AnonymousDapper

__all__ = ("MacroInterpreter", "subscript_invoke", "call_invoke", "EXPR_NODES")

import ast
from collections import deque
from copy import deepcopy

import astpretty

from micro import consts
from micro.symbol import MacroContext, SymbolTree

EXPR_NODES = [
    ast.Constant,
    ast.Name,
    ast.Lambda,
    ast.Yield,
    ast.YieldFrom,
    ast.UnaryOp,
    ast.UAdd,
    ast.USub,
    ast.Not,
    ast.Invert,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.LShift,
    ast.RShift,
    ast.BitOr,
    ast.BitXor,
    ast.BitAnd,
    ast.MatMult,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    ast.Call,
    ast.keyword,
    ast.IfExp,
    ast.Attribute,
    ast.NamedExpr,
    ast.Subscript,
    ast.Slice,
    ast.ListComp,
    ast.SetComp,
    ast.GeneratorExp,
    ast.DictComp,
    ast.comprehension
]

# builtin macros

# @macro!
def build_macro(ctx: MacroContext, node: ast.FunctionDef):
    # SymbolTree.remove_item(ctx.path, node.name)
    SymbolTree.register_macro(ctx.path, node.name, node)


SymbolTree.register_proc_macro("micro", "macro", build_macro)

# def build_proc_macro(ctx: MacroContext, node: ast.FunctionDef):
#     SymbolTree.register_proc_macro(ctx.path, node.name)


def get_arg_names(args: list[ast.arg]) -> deque[str]:
    return deque(arg.arg for arg in args)


def arg_name(item):
    match item:
        case ast.Name(id=name) | ast.Constant(value=name) | ast.arg(arg=name):
            return name

        case _:
            return repr(item)


class TupleContainer(ast.Tuple):
    @classmethod
    def __instancecheck__(cls, instance):
        return isinstance(instance, ast.Tuple)

    def __iter__(self):
        return iter(self.elts)

    def __init__(self, elts):
        self.elts = list(elts)
        self.ctx = ast.Load()

        self.__class__.__name__ = "Tuple"

        super().__init__()


class DictContainer(ast.Dict):
    @classmethod
    def __instancecheck__(cls, instance):
        return isinstance(instance, ast.Dict)

    def __iter__(self):
        return iter(self.keys)

    def __init__(self, items):
        self.keys = list(items.keys())
        self.values = list(items.values())
        self.ctx = ast.Load()

        self.__class__.__name__ = "Dict"

        super().__init__()


class MacroInterpreter(ast.NodeTransformer):
    def __init__(self, params: ast.arguments, cargs: list[ast.expr], call_kwargs: dict):
        vararg = params.vararg and params.vararg.arg or None

        kwarg = params.kwarg and params.kwarg.arg or None

        kw_defaults = deque(params.kw_defaults)
        defaults = deque(params.defaults)
        args = deque(cargs)

        # log.debug("posonlyargs", list(map(arg_name, params.posonlyargs)))
        # log.debug("args", list(map(arg_name, params.args)))
        # log.debug("kwonlyargs", list(map(arg_name, params.kwonlyargs)))

        # log.debug("\ndefaults", list(map(arg_name, defaults)))
        # log.debug("kw_defaults", list(map(arg_name, kw_defaults)))

        # log.debug("\nargs", list(map(arg_name, cargs)))
        # log.debug("kwargs", list(map(arg_name, call_kwargs)))

        call_args = {}

        for arg in get_arg_names(params.posonlyargs + params.args):
            if args:
                call_args[arg] = args.popleft()
                if defaults:
                    defaults.popleft()

            elif defaults:
                call_args[arg] = defaults.popleft()

            else:
                raise ValueError(f"positional {arg} has no passed value")

        if vararg:
            call_args[vararg] = TupleContainer(args)

        for karg in get_arg_names(params.kwonlyargs):
            if karg in call_kwargs:
                call_args[karg] = call_kwargs.pop(karg)

                if kw_defaults:
                    kw_defaults.popleft()

            elif kw_defaults:
                call_args[karg] = kw_defaults.popleft()

            else:
                raise ValueError(f"keyword {karg} has no passed value")

        if kwarg:
            call_args[kwarg] = DictContainer(call_kwargs)

        self.vars = call_args
        # print(self.vars)

        super().__init__()

    def _get_arg(self, name: str):
        # print(self.vars, name)
        return self.vars.get(name[consts.MACRO_SUBST_LEN :], None)

    def visit_Attribute(self, node: ast.Attribute):
        self.generic_visit(node)

        if node.attr.startswith(consts.MACRO_SUBST):
            if v := self._get_arg(node.attr):
                node.attr = ast.unparse(v)

        return node

    def visit_Name(self, node: ast.Name):
        if node.id.startswith(consts.MACRO_SUBST):
            ctx = node.ctx
            node = self._get_arg(node.id) or node
            node.ctx = ctx

        return node

    def visit_ClassDef(self, node: ast.ClassDef):
        self.generic_visit(node)
        if node.name.startswith(consts.MACRO_SUBST):
            if name := self._get_arg(node.name):
                node.name = name.id

        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.generic_visit(node)

        if node.name.startswith(consts.MACRO_SUBST):
            node.name = arg_name(self._get_arg(node.name))

        return node

    def visit_For(self, node: ast.For):
        self.generic_visit(node)

        match node.iter:
            case TupleContainer():
                ...

            case DictContainer():
                body = []
                match node.target:
                    case ast.Tuple(elts=[ast.Name(id=k), ast.Name(id=v)]) if k.startswith(
                        consts.MACRO_SUBST
                    ) and v.startswith(consts.MACRO_SUBST):
                        clean_k = k[consts.MACRO_SUBST_LEN :]
                        clean_v = v[consts.MACRO_SUBST_LEN :]

                        for key, value in zip(node.iter.keys, node.iter.values):  # type: ignore
                            self.vars[clean_k] = key
                            self.vars[clean_v] = value

                            body.append(self.visit(deepcopy(node.body[0])))

                        del self.vars[clean_k]
                        del self.vars[clean_v]
                        return body


        # for idx, stmt in enumerate(node.body):
        #     if type(stmt) in EXPR_NODES:
        #         node.body[idx] = ast.Expr(value=stmt)

        return node



def subscript_invoke(node: ast.Subscript, macro: ast.FunctionDef):
    args = []
    kwargs = {}
    if isinstance(node.slice, ast.Tuple):
        args.extend(node.slice.elts)

    elif isinstance(node.slice, ast.Slice):
        if node.slice.step is not None:
            kwargs["step"] = node.slice.step

        if node.slice.upper is not None:
            kwargs["upper"] = node.slice.upper

        if node.slice.lower is not None:
            kwargs["lower"] = node.slice.lower

    else:
        args.append(node.slice)

    interpreter = MacroInterpreter(macro.args, args, kwargs)
    tree = interpreter.visit(macro)

    return tree.body


def call_invoke(node: ast.Call, macro: ast.FunctionDef):
    args = node.args
    kwargs = {ast.Name(id=k.arg, ctx=ast.Load()): k.value for k in node.keywords}

    interpreter = MacroInterpreter(macro.args, args, kwargs)
    tree = interpreter.visit(macro)

    # astpretty.pprint(tree, show_offsets=False)

    return tree.body
