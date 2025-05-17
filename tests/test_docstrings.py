import doctest
import importlib
import pkgutil
import types
import typing as t

import neverraise


def test_docstrings():
    def iter_modules(package: types.ModuleType) -> t.Generator[types.ModuleType]:
        if not hasattr(package, "__path__"):
            return
        for _, name, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            try:
                module = importlib.import_module(name)
                yield module
                if ispkg:
                    yield from iter_modules(module)
            except Exception as e:
                print(f"Skipping {name} due to import error: {e}")

    verbose = True

    res = doctest.testmod(neverraise, verbose=verbose)
    assert res.failed == 0

    for module in iter_modules(neverraise):
        res = doctest.testmod(module, verbose=verbose)
        assert res.failed == 0
