from __future__ import annotations

from typing import (
    TypeVar,
    Generic,
    Callable,
    Any,
    cast,
    TypeAlias,
    Awaitable,
)

T = TypeVar("T", covariant=True)
U = TypeVar("U", covariant=True)

E = TypeVar("E", covariant=True, bound=BaseException)
F = TypeVar("F", covariant=True, bound=BaseException)

A = TypeVar(
    "A",
)
R = TypeVar(
    "R",
)


class Ok(Generic[T]):
    """Ok variant of Result."""

    __slots__ = ("_value",)
    __match_args__ = ("_value",)

    _value: T

    def __init__(self, value: T):
        self._value = value

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def map(self, func: Callable[[T], U]) -> Result[U, E]:
        return Ok(func(self._value))

    def map_err(self, func: Callable[[E], F]) -> Ok[T]:
        return Ok(self._value)

    def and_then(self, func: Callable[[T], Result[U, F]]) -> Result[U, F]:
        return func(self._value)

    def and_tee(self, func: Callable[[T], Any]) -> Ok[T]:
        try:
            func(self._value)
        except Exception:
            # Tee doesn't care about the error
            pass
        return self

    def and_through(
        self, func: Callable[[Any], U], error_handler: Callable[[Exception], F]
    ) -> Result[U, E | F]:
        try:
            return Ok(func(self._value))
        except Exception as e:
            return Err(error_handler(e))

    def or_tee(self, func: Callable[[E], Any]) -> Result[T, E]:
        return Ok(self._value)

    def or_else(self, func: Callable[[E], Result[U, F]]) -> Result[T | U, F]:
        return Ok(self._value)

    # def async_and_then(
    #     self, func: Callable[[T], ResultAsync[U, F]]
    # ) -> ResultAsync[U, E | F]:
    #     return func(self._value)

    # def async_map(self, func: Callable[[T], asyncio.Future[U]]) -> ResultAsync[U, E]:
    #     return ResultAsync.from_safe_promise(func(self._value))

    def unwrap_or(self, default: A) -> T | A:
        return self._value

    def __str__(self) -> str:
        return f"Ok({self._value})"

    def __repr__(self) -> str:
        return f"Ok({self._value!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Ok):
            return False
        other_ok = cast(Ok[Any], other)
        return self._value == other_ok._value


class Err(Generic[E]):
    """Err variant of Result."""

    __slots__ = ("_error",)
    __match_args__ = ("_error",)

    _error: E

    def __init__(self, error: E):
        self._error = error

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def map(self, func: Callable[[T], U]) -> Err[E]:
        return Err(self._error)

    def map_err(self, func: Callable[[E], F]) -> Err[F]:
        return Err(func(self._error))

    def and_then(self, func: Callable[[T], Result[U, F]]) -> Result[U, E | F]:
        return Err(self._error)

    def and_tee(self, func: Callable[[T], Any]) -> Result[T, E]:
        return Err(self._error)

    def and_through(
        self, func: Callable[[Any], U], error_handler: Callable[[Exception], F]
    ) -> Result[U, E | F]:
        return self

    def or_tee(self, func: Callable[[E], Any]) -> Result[T, E]:
        try:
            func(self._error)
        except Exception:
            # Tee doesn't care about the error
            pass
        return Err(self._error)

    def or_else(self, func: Callable[[E], Result[U, F]]) -> Result[T | U, F]:
        return func(self._error)

    # def async_and_then(
    #     self, func: Callable[[T], ResultAsync[U, F]]
    # ) -> ResultAsync[U, E | F]:
    #     return ResultAsync.err(self._error)
    #
    # def async_map(self, func: Callable[[T], asyncio.Future[U]]) -> ResultAsync[U, E]:
    #     return ResultAsync.err(self._error)

    def unwrap_or(self, default: A) -> A:
        return default

    def __str__(self) -> str:
        return f"Err({self._error})"

    def __repr__(self) -> str:
        return f"Err({self._error!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Err):
            return False
        other_err = cast(Err[Any], other)
        return self._error == other_err._error


Result: TypeAlias = Ok[T] | Err[E]


def try_catch(func: Callable[[], T]) -> Result[T, BaseException]:
    try:
        return Ok(func())
    except BaseException as e:
        return Err(e)


class ResultAsync(Generic[T, E]):
    __slots__ = ("coro",)

    coro: Awaitable[Result[T, E]]

    def __init__(self, coro: Awaitable[Result[T, E]]) -> None:
        self.coro = coro

    @staticmethod
    def from_coro(
        coro: Awaitable[U], error_handler: Callable[[BaseException], F]
    ) -> ResultAsync[U, F]:
        async def wrapper():
            try:
                return Ok(await coro)
            except Exception as e:
                return Err(error_handler(e))

        return ResultAsync(wrapper())

    # @classmethod
    # def from_coro(
    #     cls: type[ResultAsync[T, E]],
    #     coro: Awaitable[T],
    #     error_handler: Callable[[Exception], E],
    # ) -> ResultAsync[T, E]:
    #     async def wrapper():
    #         try:
    #             value = await coro
    #             return Ok(value)
    #         except Exception as e:
    #             return Err(error_handler(e))

    #     return cls(wrapper())

    def map(self, func: Callable[[T], U]) -> ResultAsync[U, E]:
        async def wraper():
            result = await self.coro
            match result:
                case Ok(value):
                    return Ok(func(value))
                case Err(error):
                    return Err(error)

        return ResultAsync(wraper())

    def map_async(self, func: Callable[[T], Awaitable[U]]) -> ResultAsync[U, E]:
        async def wraper():
            match await self.coro:
                case Ok(value):
                    return Ok(await func(value))
                case Err(error):
                    return Err(error)

        return ResultAsync(wraper())

    def and_through(
        self, func: Callable[[T], U], error_handler: Callable[[Exception], F]
    ) -> ResultAsync[U, E | F]:
        async def wraper():
            result = await self.coro
            match result:
                case Ok(value):
                    ...
                case Err() as err:
                    return err
            try:
                return Ok(func(value))
            except Exception as e:
                return Err(error_handler(e))

        return ResultAsync(wraper())

    def __await__(self):
        return self.coro.__await__()


class ResultFactory:
    @staticmethod
    def from_func(
        func: Callable[[], T], error_handler: Callable[[Exception], E]
    ) -> Result[T, E]:
        try:
            return Ok(func())
        except Exception as e:
            return Err(error_handler(e))

    @staticmethod
    def from_coro(
        coro: Awaitable[T],
        error_handler: Callable[[Exception], E],
    ) -> ResultAsync[T, E]:
        async def wrapper():
            try:
                value = await coro
                return Ok(value)
            except Exception as e:
                return Err(error_handler(e))

        return ResultAsync(wrapper())
