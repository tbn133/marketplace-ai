"""Language registry — maps file extensions to tree-sitter languages and AST extraction rules.

Each language defines which AST node types represent functions, classes, imports, and calls.
Grammars are loaded dynamically; missing packages are silently skipped.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from tree_sitter import Language

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LangRules:
    """AST node type mappings for a language."""

    func_types: frozenset[str]
    class_types: frozenset[str]
    import_types: frozenset[str]
    call_types: frozenset[str]
    name_field: str = "name"
    params_field: str = "parameters"
    return_field: str | None = "return_type"
    func_keyword: str = "def"
    # For languages where imports use different field names
    import_module_field: str = "module_name"
    # Node types to recurse into for class body (methods)
    class_body_type: str = "block"


@dataclass
class LangSpec:
    """A registered language with its tree-sitter Language and extraction rules."""

    language: Language
    rules: LangRules
    extensions: tuple[str, ...]


# -- Language rules definitions --

PYTHON_RULES = LangRules(
    func_types=frozenset({"function_definition"}),
    class_types=frozenset({"class_definition"}),
    import_types=frozenset({"import_statement", "import_from_statement"}),
    call_types=frozenset({"call"}),
    name_field="name",
    params_field="parameters",
    return_field="return_type",
    func_keyword="def",
    import_module_field="module_name",
    class_body_type="block",
)

TYPESCRIPT_RULES = LangRules(
    func_types=frozenset({"function_declaration", "method_definition", "arrow_function"}),
    class_types=frozenset({"class_declaration"}),
    import_types=frozenset({"import_statement"}),
    call_types=frozenset({"call_expression"}),
    name_field="name",
    params_field="parameters",
    return_field="return_type",
    func_keyword="function",
    import_module_field="source",
    class_body_type="class_body",
)

JAVASCRIPT_RULES = LangRules(
    func_types=frozenset({"function_declaration", "method_definition", "arrow_function"}),
    class_types=frozenset({"class_declaration"}),
    import_types=frozenset({"import_statement"}),
    call_types=frozenset({"call_expression"}),
    name_field="name",
    params_field="parameters",
    return_field=None,
    func_keyword="function",
    import_module_field="source",
    class_body_type="class_body",
)

GO_RULES = LangRules(
    func_types=frozenset({"function_declaration", "method_declaration"}),
    class_types=frozenset({"type_declaration"}),
    import_types=frozenset({"import_declaration"}),
    call_types=frozenset({"call_expression"}),
    name_field="name",
    params_field="parameters",
    return_field="result",
    func_keyword="func",
    import_module_field="path",
    class_body_type="field_declaration_list",
)

RUST_RULES = LangRules(
    func_types=frozenset({"function_item"}),
    class_types=frozenset({"struct_item", "impl_item", "enum_item"}),
    import_types=frozenset({"use_declaration"}),
    call_types=frozenset({"call_expression"}),
    name_field="name",
    params_field="parameters",
    return_field="return_type",
    func_keyword="fn",
    import_module_field="argument",
    class_body_type="declaration_list",
)

JAVA_RULES = LangRules(
    func_types=frozenset({"method_declaration", "constructor_declaration"}),
    class_types=frozenset({"class_declaration", "interface_declaration", "enum_declaration"}),
    import_types=frozenset({"import_declaration"}),
    call_types=frozenset({"method_invocation"}),
    name_field="name",
    params_field="formal_parameters",
    return_field="type",
    func_keyword="",
    import_module_field="",
    class_body_type="class_body",
)

CPP_RULES = LangRules(
    func_types=frozenset({"function_definition"}),
    class_types=frozenset({"class_specifier", "struct_specifier"}),
    import_types=frozenset({"preproc_include"}),
    call_types=frozenset({"call_expression"}),
    name_field="declarator",
    params_field="parameters",
    return_field="type",
    func_keyword="",
    import_module_field="path",
    class_body_type="field_declaration_list",
)

C_RULES = LangRules(
    func_types=frozenset({"function_definition"}),
    class_types=frozenset({"struct_specifier"}),
    import_types=frozenset({"preproc_include"}),
    call_types=frozenset({"call_expression"}),
    name_field="declarator",
    params_field="parameters",
    return_field="type",
    func_keyword="",
    import_module_field="path",
    class_body_type="field_declaration_list",
)

# -- Registry: extension -> LangSpec --

_REGISTRY: dict[str, LangSpec] = {}


def _try_register(
    module_name: str,
    lang_attr: str,
    rules: LangRules,
    extensions: tuple[str, ...],
) -> None:
    """Try to import a tree-sitter grammar and register it."""
    try:
        import importlib
        mod = importlib.import_module(module_name)
        lang_fn = getattr(mod, lang_attr, None) or getattr(mod, "language")
        language = Language(lang_fn())
        spec = LangSpec(language=language, rules=rules, extensions=extensions)
        for ext in extensions:
            _REGISTRY[ext] = spec
        logger.debug("Registered language: %s (%s)", module_name, ", ".join(extensions))
    except (ImportError, AttributeError, Exception) as e:
        logger.debug("Skipped %s: %s", module_name, e)


def _init_registry() -> None:
    """Load all available tree-sitter grammars."""
    if _REGISTRY:
        return

    _try_register("tree_sitter_python", "language", PYTHON_RULES, (".py",))
    _try_register("tree_sitter_typescript", "language_typescript", TYPESCRIPT_RULES, (".ts",))
    _try_register("tree_sitter_typescript", "language_tsx", TYPESCRIPT_RULES, (".tsx",))
    _try_register("tree_sitter_javascript", "language", JAVASCRIPT_RULES, (".js", ".jsx", ".mjs", ".cjs"))
    _try_register("tree_sitter_go", "language", GO_RULES, (".go",))
    _try_register("tree_sitter_rust", "language", RUST_RULES, (".rs",))
    _try_register("tree_sitter_java", "language", JAVA_RULES, (".java",))
    _try_register("tree_sitter_cpp", "language", CPP_RULES, (".cpp", ".cc", ".cxx", ".hpp", ".hxx"))
    _try_register("tree_sitter_c", "language", C_RULES, (".c", ".h"))


def get_registry() -> dict[str, LangSpec]:
    """Return the language registry, initializing it on first call."""
    _init_registry()
    return _REGISTRY


def get_supported_extensions() -> set[str]:
    """Return all file extensions with an available grammar."""
    return set(get_registry().keys())


def get_lang_spec(extension: str) -> LangSpec | None:
    """Look up a language spec by file extension."""
    return get_registry().get(extension)
