"""Parse function signatures without executing annotations or defaults."""

from __future__ import annotations

import ast
import inspect

from pyfuncai.exceptions import ConfigurationError


def parse_signature(signature: str) -> ast.FunctionDef:
    """Accept one signature with literal defaults and inert type annotations."""

    if not isinstance(signature, str) or len(signature) > 4096:
        raise ConfigurationError(
            "signature must be a string of at most 4096 characters."
        )
    try:
        module = ast.parse(f"def __temp{signature}:\n    pass\n")
        if len(module.body) != 1 or not isinstance(module.body[0], ast.FunctionDef):
            raise ValueError("Expected one function signature.")
        function = module.body[0]
        if (
            function.name != "__temp"
            or function.decorator_list
            or len(function.body) != 1
            or not isinstance(function.body[0], ast.Pass)
            or getattr(function, "type_params", [])
        ):
            raise ValueError("Function bodies and decorators are not allowed.")
        # Compile only to check Python's parameter ordering and duplicate names.
        # Compiling does not execute defaults, annotations, or a function body.
        compile(module, "<pyfuncai-signature>", "exec")
        for default in function.args.defaults + [
            node for node in function.args.kw_defaults if node is not None
        ]:
            if any(
                isinstance(node, (ast.Call, ast.Attribute, ast.Name))
                for node in ast.walk(default)
            ):
                raise ValueError(
                    "Defaults must be literals, not executable expressions."
                )
            ast.literal_eval(default)
        annotations = [
            node.annotation
            for node in ast.walk(function.args)
            if isinstance(node, ast.arg) and node.annotation is not None
        ]
        if function.returns is not None:
            annotations.append(function.returns)
        allowed = (
            ast.Name,
            ast.Attribute,
            ast.Subscript,
            ast.Tuple,
            ast.List,
            ast.Constant,
            ast.BinOp,
            ast.BitOr,
            ast.Load,
            ast.Starred,
        )
        if any(
            not isinstance(node, allowed)
            for annotation in annotations
            for node in ast.walk(annotation)
        ):
            raise ValueError(
                "Annotations must be type expressions, not executable expressions."
            )
    except (SyntaxError, ValueError, TypeError, RecursionError) as error:
        raise ConfigurationError(
            "Invalid signature: use Python parameters, literal defaults, and type annotations."
        ) from error
    return function


def signature_object(signature: str) -> inspect.Signature:
    """Create inspect metadata using AST strings and literal values only."""

    function = parse_signature(signature)
    args = function.args
    parameters = []
    positional = args.posonlyargs + args.args
    defaults = [inspect.Parameter.empty] * (len(positional) - len(args.defaults))
    defaults += [ast.literal_eval(node) for node in args.defaults]

    def add(arg: ast.arg, kind: inspect._ParameterKind, default: object) -> None:
        annotation = (
            inspect.Parameter.empty
            if arg.annotation is None
            else ast.unparse(arg.annotation)
        )
        parameters.append(
            inspect.Parameter(arg.arg, kind, default=default, annotation=annotation)
        )

    for index, (arg, default) in enumerate(zip(positional, defaults)):
        kind = (
            inspect.Parameter.POSITIONAL_ONLY
            if index < len(args.posonlyargs)
            else inspect.Parameter.POSITIONAL_OR_KEYWORD
        )
        add(arg, kind, default)
    if args.vararg:
        add(args.vararg, inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.empty)
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        add(
            arg,
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.empty if default is None else ast.literal_eval(default),
        )
    if args.kwarg:
        add(args.kwarg, inspect.Parameter.VAR_KEYWORD, inspect.Parameter.empty)
    returns = (
        inspect.Signature.empty
        if function.returns is None
        else ast.unparse(function.returns)
    )
    return inspect.Signature(parameters, return_annotation=returns)
