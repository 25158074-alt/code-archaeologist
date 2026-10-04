from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import tree_sitter
from tree_sitter import Language, Node, Parser, Tree

try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_typescript as tstypescript
    import tree_sitter_go as tsgo
    import tree_sitter_rust as tsrust
except ImportError:
    tspython = tsjavascript = tstypescript = tsgo = tsrust = None


@dataclass(slots=True)
class ParsedFile:
    path: str
    language: str
    content: str
    tree: Tree
    functions: list[dict[str, Any]] = None
    classes: list[dict[str, Any]] = None
    imports: list[dict[str, Any]] = None
    comments: list[dict[str, Any]] = None
    complexity: int = 0
    lines_of_code: int = 0
    last_modified: datetime | None = None
    author: str | None = None

    def __post_init__(self):
        if self.functions is None:
            self.functions = []
        if self.classes is None:
            self.classes = []
        if self.imports is None:
            self.imports = []
        if self.comments is None:
            self.comments = []


class LanguageParser(ABC):
    @property
    @abstractmethod
    def language_name(self) -> str: ...

    @property
    @abstractmethod
    def file_extensions(self) -> list[str]: ...

    @abstractmethod
    def get_language(self) -> Language: ...

    def parse(self, content: str, path: str) -> ParsedFile:
        parser = Parser(self.get_language())
        tree = parser.parse(bytes(content, "utf8"))

        parsed = ParsedFile(
            path=path,
            language=self.language_name,
            content=content,
            tree=tree,
            lines_of_code=len(content.splitlines()),
        )

        self._extract_nodes(parsed)
        parsed.complexity = self._calculate_complexity(tree.root_node)
        return parsed

    @abstractmethod
    def _extract_nodes(self, parsed: ParsedFile) -> None: ...

    def _calculate_complexity(self, node: Node) -> int:
        complexity_types = self._complexity_nodes()
        complexity = 1
        stack = [node]
        while stack:
            current = stack.pop()
            for child in current.children:
                if child.type in complexity_types:
                    complexity += 1
                stack.append(child)
        return complexity

    @abstractmethod
    def _complexity_nodes(self) -> set[str]: ...

    def _get_node_text(self, node: Node, content: str) -> str:
        # tree-sitter offsets are UTF-8 byte offsets, not str indices
        return (node.text or b"").decode("utf8", errors="replace")

    def _walk(self, node: Node) -> Iterator[Node]:
        stack = [node]
        while stack:
            current = stack.pop()
            yield current
            stack.extend(reversed(current.children))


class PythonParser(LanguageParser):
    @property
    def language_name(self) -> str:
        return "python"

    @property
    def file_extensions(self) -> list[str]:
        return [".py"]

    def get_language(self) -> Language:
        if tspython is None:
            raise RuntimeError("tree-sitter-python not installed")
        return Language(tspython.language())

    def _extract_nodes(self, parsed: ParsedFile) -> None:
        for node in self._walk(parsed.tree.root_node):
            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    parsed.functions.append({
                        "name": self._get_node_text(name_node, parsed.content),
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                        "start_col": node.start_point[1],
                        "end_col": node.end_point[1],
                        "decorators": self._get_decorators(node, parsed.content),
                        "async": any(c.type == "async" for c in node.children),
                    })
            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    parsed.classes.append({
                        "name": self._get_node_text(name_node, parsed.content),
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                        "methods": self._get_methods(node, parsed.content),
                        "bases": self._get_bases(node, parsed.content),
                    })
            elif node.type in ("import_statement", "import_from_statement"):
                parsed.imports.append({
                    "type": node.type,
                    "text": self._get_node_text(node, parsed.content),
                    "line": node.start_point[0] + 1,
                })
            elif node.type == "comment":
                parsed.comments.append({
                    "text": self._get_node_text(node, parsed.content),
                    "line": node.start_point[0] + 1,
                })

    def _get_decorators(self, node: Node, content: str) -> list[str]:
        decorators = []
        for child in node.children:
            if child.type == "decorator":
                decorators.append(self._get_node_text(child, content))
        return decorators

    def _get_methods(self, node: Node, content: str) -> list[dict[str, Any]]:
        methods = []
        for child in node.children:
            if child.type == "block":
                for grandchild in child.children:
                    if grandchild.type == "decorated_definition":
                        grandchild = grandchild.child_by_field_name("definition") or grandchild
                    if grandchild.type == "function_definition":
                        name_node = grandchild.child_by_field_name("name")
                        if name_node:
                            methods.append({
                                "name": self._get_node_text(name_node, content),
                                "start_line": grandchild.start_point[0] + 1,
                                "end_line": grandchild.end_point[0] + 1,
                            })
        return methods

    def _get_bases(self, node: Node, content: str) -> list[str]:
        bases = []
        for child in node.children:
            if child.type == "argument_list":
                for grandchild in child.children:
                    if grandchild.type not in ("(", ")", ","):
                        bases.append(self._get_node_text(grandchild, content))
        return bases

    def _complexity_nodes(self) -> set[str]:
        return {
            "if_statement", "while_statement", "for_statement", "try_statement",
            "except_clause", "with_statement", "match_statement", "case_pattern",
            "boolean_operator", "conditional_expression",
        }


class JavaScriptParser(LanguageParser):
    @property
    def language_name(self) -> str:
        return "javascript"

    @property
    def file_extensions(self) -> list[str]:
        return [".js", ".jsx", ".mjs", ".cjs"]

    def get_language(self) -> Language:
        if tsjavascript is None:
            raise RuntimeError("tree-sitter-javascript not installed")
        return Language(tsjavascript.language())

    def _extract_nodes(self, parsed: ParsedFile) -> None:
        for node in self._walk(parsed.tree.root_node):
            if node.type in ("function_declaration", "function_expression", "function", "arrow_function"):
                name = self._extract_function_name(node, parsed.content)
                if name:
                    parsed.functions.append({
                        "name": name,
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                        "async": any(c.type == "async" for c in node.children),
                        "generator": any(c.type == "*" for c in node.children),
                    })
            elif node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    parsed.classes.append({
                        "name": self._get_node_text(name_node, parsed.content),
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                        "methods": self._get_js_methods(node, parsed.content),
                    })
            elif node.type in ("import_statement", "import_declaration"):
                parsed.imports.append({
                    "type": node.type,
                    "text": self._get_node_text(node, parsed.content),
                    "line": node.start_point[0] + 1,
                })
            elif node.type == "comment":
                parsed.comments.append({
                    "text": self._get_node_text(node, parsed.content),
                    "line": node.start_point[0] + 1,
                })

    def _extract_function_name(self, node: Node, content: str) -> str | None:
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                return self._get_node_text(name_node, content)
        elif node.type in ("function_expression", "function", "arrow_function"):
            parent = node.parent
            if parent and parent.type == "variable_declarator":
                name_node = parent.child_by_field_name("name")
                if name_node:
                    return self._get_node_text(name_node, content)
        return None

    def _get_js_methods(self, node: Node, content: str) -> list[dict[str, Any]]:
        methods = []
        for child in self._walk(node):
            if child.type in ("method_definition", "public_field_definition"):
                name_node = child.child_by_field_name("name")
                if name_node:
                    methods.append({
                        "name": self._get_node_text(name_node, content),
                        "start_line": child.start_point[0] + 1,
                        "end_line": child.end_point[0] + 1,
                    })
        return methods

    def _complexity_nodes(self) -> set[str]:
        return {
            "if_statement", "while_statement", "for_statement", "for_in_statement",
            "for_of_statement", "try_statement", "catch_clause", "switch_statement",
            "case_clause", "conditional_expression", "logical_expression",
        }


class TypeScriptParser(JavaScriptParser):
    @property
    def language_name(self) -> str:
        return "typescript"

    @property
    def file_extensions(self) -> list[str]:
        return [".ts", ".tsx"]

    def get_language(self) -> Language:
        if tstypescript is None:
            raise RuntimeError("tree-sitter-typescript not installed")
        return Language(tstypescript.language_typescript())


class GoParser(LanguageParser):
    @property
    def language_name(self) -> str:
        return "go"

    @property
    def file_extensions(self) -> list[str]:
        return [".go"]

    def get_language(self) -> Language:
        if tsgo is None:
            raise RuntimeError("tree-sitter-go not installed")
        return Language(tsgo.language())

    def _extract_nodes(self, parsed: ParsedFile) -> None:
        for node in self._walk(parsed.tree.root_node):
            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    parsed.functions.append({
                        "name": self._get_node_text(name_node, parsed.content),
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                    })
            elif node.type == "type_declaration":
                for spec in node.children:
                    if spec.type == "type_spec":
                        name_node = spec.child_by_field_name("name")
                        if name_node:
                            parsed.classes.append({
                                "name": self._get_node_text(name_node, parsed.content),
                                "start_line": node.start_point[0] + 1,
                                "end_line": node.end_point[0] + 1,
                            })
            elif node.type == "import_declaration":
                parsed.imports.append({
                    "type": node.type,
                    "text": self._get_node_text(node, parsed.content),
                    "line": node.start_point[0] + 1,
                })
            elif node.type == "comment":
                parsed.comments.append({
                    "text": self._get_node_text(node, parsed.content),
                    "line": node.start_point[0] + 1,
                })

    def _complexity_nodes(self) -> set[str]:
        return {
            "if_statement", "for_statement", "range_clause", "switch_statement",
            "case_clause", "select_statement", "comm_case",
        }


class RustParser(LanguageParser):
    @property
    def language_name(self) -> str:
        return "rust"

    @property
    def file_extensions(self) -> list[str]:
        return [".rs"]

    def get_language(self) -> Language:
        if tsrust is None:
            raise RuntimeError("tree-sitter-rust not installed")
        return Language(tsrust.language())

    def _extract_nodes(self, parsed: ParsedFile) -> None:
        for node in self._walk(parsed.tree.root_node):
            if node.type == "function_item":
                name_node = node.child_by_field_name("name")
                if name_node:
                    parsed.functions.append({
                        "name": self._get_node_text(name_node, parsed.content),
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                        "async": any(c.type == "async" for c in node.children),
                    })
            elif node.type in ("struct_item", "enum_item", "trait_item", "impl_item"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    parsed.classes.append({
                        "name": self._get_node_text(name_node, parsed.content),
                        "type": node.type,
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                    })
            elif node.type == "use_declaration":
                parsed.imports.append({
                    "type": node.type,
                    "text": self._get_node_text(node, parsed.content),
                    "line": node.start_point[0] + 1,
                })
            elif node.type == "line_comment":
                parsed.comments.append({
                    "text": self._get_node_text(node, parsed.content),
                    "line": node.start_point[0] + 1,
                })

    def _complexity_nodes(self) -> set[str]:
        return {
            "if_expression", "while_expression", "for_expression", "loop_expression",
            "match_expression", "match_arm", "try_expression", "catch_expression",
        }


PARSERS: dict[str, LanguageParser] = {
    "python": PythonParser(),
    "javascript": JavaScriptParser(),
    "typescript": TypeScriptParser(),
    "go": GoParser(),
    "rust": RustParser(),
}


def get_parser_for_file(path: str) -> LanguageParser | None:
    ext = Path(path).suffix.lower()
    for parser in PARSERS.values():
        if ext in parser.file_extensions:
            return parser
    return None


def get_parser_for_language(language: str) -> LanguageParser | None:
    return PARSERS.get(language.lower())