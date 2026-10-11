#!/usr/bin/env python3
"""Insert the one hook line into upstream's create_app (app/__init__.py).

    scripts/insert_hook.py <upstream-checkout>          # insert (idempotent)
    scripts/insert_hook.py --check <upstream-checkout>  # exit 1 unless it's in place

Finds create_app with Python's own parser and puts the line before each `return app`
in it, at that statement's indentation, wherever upstream has moved it.
"""
import ast
import sys

HOOK = 'from .scrapers import directv_heaac; directv_heaac.install(app)  # fastchannels-heaac: DirecTV HE-AAC audio'
PATH = 'app/__init__.py'


def _returns(fn):
    out, todo = [], list(fn.body)
    while todo:
        node = todo.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Name) and node.value.id == 'app':
            out.append(node)
        todo.extend(ast.iter_child_nodes(node))
    return out


def main(argv) -> int:
    check = '--check' in argv
    args = [a for a in argv if a != '--check']
    if len(args) != 1:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    path = f'{args[0].rstrip("/")}/{PATH}'
    src = open(path, encoding='utf-8').read()
    if HOOK in src:
        print(f'{PATH}: the hook is in create_app.')
        return 0
    if check:
        print(f'::error::{PATH}: the hook is not in create_app')
        return 1
    tree = ast.parse(src)
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'create_app'), None)
    if fn is None:
        print(f'::error::{PATH} has no module-level create_app; update scripts/insert_hook.py')
        return 1
    lines = src.splitlines(keepends=True)
    spots = sorted({r.lineno for r in _returns(fn)
                    if lines[r.lineno - 1][r.col_offset:].lstrip().startswith('return')}, reverse=True)
    if not spots:
        print(f'::error::create_app in {PATH} no longer ends in `return app`; update scripts/insert_hook.py')
        return 1
    for lineno in spots:
        line = lines[lineno - 1]
        indent = line[:len(line) - len(line.lstrip())]
        lines.insert(lineno - 1, f'{indent}{HOOK}\n')
    open(path, 'w', encoding='utf-8').write(''.join(lines))
    print(f'{PATH}: inserted the hook before {len(spots)} `return app` in create_app.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
