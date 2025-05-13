import typing as t
import nox

def nox_session(**kwargs: t.Any) -> t.Callable[[t.Callable[[nox.Session], None]], t.Callable[[nox.Session], None]]:
    kwargs.setdefault("venv_backend", "uv")
    kwargs.setdefault("reuse_venv", True)

    def inner(func: t.Callable[[nox.Session], None]) -> t.Callable[[nox.Session], None]:
        return nox.session(**kwargs)(func)

    return inner

@nox_session()
def test(session: nox.Session) -> None:
    session.run_install(
        "uv",
        "sync",
        "--group=test",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.run("python", "-m", "pytest", "--cov=neverraise", "--cov-report=term-missing")

@nox_session()
def lint(session: nox.Session) -> None:
    session.run_install(
        "uv",
        "sync",
        "--group=lint",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.run("python", "-m", "ruff", "check", "--fix", "src", "tests")