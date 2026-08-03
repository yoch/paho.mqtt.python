from __future__ import annotations

import ast
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "mqttnext"


@dataclass(frozen=True)
class FunctionMetric:
    path: Path
    name: str
    first_line: int
    last_line: int
    statements: int
    branches: int
    awaits: int

    @property
    def lines(self) -> int:
        return self.last_line - self.first_line + 1


def iter_python_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def function_metrics(path: Path, tree: ast.AST) -> list[FunctionMetric]:
    metrics: list[FunctionMetric] = []
    branch_nodes = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.Match,
        ast.IfExp,
        ast.comprehension,
    )
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        metrics.append(
            FunctionMetric(
                path=path.relative_to(ROOT),
                name=node.name,
                first_line=node.lineno,
                last_line=getattr(node, "end_lineno", node.lineno),
                statements=sum(isinstance(child, ast.stmt) for child in ast.walk(node)),
                branches=sum(isinstance(child, branch_nodes) for child in ast.walk(node)),
                awaits=sum(isinstance(child, ast.Await) for child in ast.walk(node)),
            )
        )
    return metrics


def exact_duplicate_functions(
    functions: list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]],
) -> list[list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]]]:
    grouped: dict[str, list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]]] = defaultdict(list)
    for path, node in functions:
        if len(node.body) < 2:
            continue
        body = ast.Module(body=node.body, type_ignores=[])
        grouped[ast.dump(body, annotate_fields=True, include_attributes=False)].append((path, node))
    return [group for group in grouped.values() if len(group) > 1]


def main() -> None:
    metrics: list[FunctionMetric] = []
    functions: list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    literals: Counter[str] = Counter()
    module_sizes: list[tuple[int, Path]] = []

    for path in iter_python_files():
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
        module_sizes.append((source.count("\n") + 1, path.relative_to(ROOT)))
        metrics.extend(function_metrics(path, tree))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append((path.relative_to(ROOT), node))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value.strip()
                if len(value) >= 18 and " " in value and "\n" not in value:
                    literals[value] += 1

    print("# mqttnext cleanup audit\n")
    print("## Largest modules\n")
    for lines, path in sorted(module_sizes, reverse=True)[:12]:
        print(f"- `{path}`: {lines} lines")

    print("\n## High-complexity functions\n")
    candidates = [metric for metric in metrics if metric.lines >= 45 or metric.branches >= 10]
    for metric in sorted(candidates, key=lambda item: (item.branches, item.lines), reverse=True):
        print(
            f"- `{metric.path}:{metric.first_line}` `{metric.name}`: "
            f"{metric.lines} lines, {metric.statements} statements, "
            f"{metric.branches} branches, {metric.awaits} awaits"
        )

    print("\n## Exact duplicate function bodies\n")
    duplicates = exact_duplicate_functions(functions)
    if not duplicates:
        print("- none")
    for group in duplicates:
        refs = ", ".join(f"`{path}:{node.lineno}` `{node.name}`" for path, node in group)
        print(f"- {refs}")

    print("\n## Repeated long literals\n")
    repeated = [(count, value) for value, count in literals.items() if count >= 3]
    if not repeated:
        print("- none")
    for count, value in sorted(repeated, reverse=True)[:30]:
        print(f"- {count}× `{value}`")


if __name__ == "__main__":
    main()
