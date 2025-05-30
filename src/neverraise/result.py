"""Error handling with the `Result` type.

Adapted from
[the Rust `Result` type](https://doc.rust-lang.org/std/result/index.html) and
[neverthrow](https://github.com/supermacro/neverthrow/tree/master)

`Result[T, E]` is the type used for returning and propagating errors. It is a
union type with the variants, `Ok[T]`, representing success and containing a
value, and `Err[E]`, representing error and containing an error value.

```python
Result: TypeAlias = Ok[T] | Err[E]
```

Functions return Result whenever errors are expected and recoverable.

A simple function returning Result might be defined and used like so:

```python
>>> from enum import auto, Enum
>>> class Version(Enum):
...     Version1 = auto()
...     Version2 = auto()
...
>>> def parse_version(header: bytearray) -> Result[Version, str]:
...     match try_except(lambda: header[0]):
...         case Err(_):
...             return Err("invalid header length")
...         case Ok(1):
...             return Ok(Version.Version1)
...         case Ok(2):
...             return Ok(Version.Version2)
...         case Ok():
...             return Err("invalid version")
...
>>> version = parse_version(bytearray([1, 2, 3, 4]))
>>> match version:
...     case Ok(v):
...         print(f"working with version: {v}")
...     case Err(e):
...         print(f"error parsing header: {e}")
working with version: Version.Version1

```

Pattern matching on `Result`s is clear and straightforward for simple cases, but
`Result` comes with some convenience methods that make working with it more
succinct.

```python
>>> # The `is_ok` and `is_err` methods do what they say.
>>> good_result: Result[int, int] = Ok(10)
>>> bad_result: Result[int, int] = Err(10)
>>> assert good_result.is_ok() and not good_result.is_err()
>>> assert bad_result.is_err() and not bad_result.is_ok()

>>> # `map` and `map_err` consume the `Result` and produce another.
>>> good_result: Result[int, int] = good_result.map(lambda i: i + 1)
>>> bad_result: Result[int, int] = bad_result.map_err(lambda i: i - 1)
>>> assert good_result == Ok(11)
>>> assert bad_result == Err(9)

>>> # Use `and_then` to continue the computation.
>>> good_result: Result[bool, int] = good_result.and_then(lambda i: Ok(i == 11))
>>> assert good_result == Ok(True)

>>> # Use `or_else` to handle the error.
>>> bad_result: Result[int, int] = bad_result.or_else(lambda i: Ok(i + 20))
>>> assert bad_result == Ok(29)

>>> # Consume the result and return the contents with `unwrap`.
>>> final_awesome_result = good_result.unwrap()
>>> assert final_awesome_result

```

## Results must be used

A common problem with using return values to indicate errors is that it is easy
to ignore the return value, thus failing to handle the error. Enable the following in `pyrightconfig.json` to get errors

```json
{
  "typeCheckingMode": "strict",
  "reportMatchNotExhaustive": "error",
  "reportUnusedCallResult": "error",
  "reportUnusedCoroutine": "error"
}
```

This makes Result especially useful with functions that may encounter errors but don't otherwise return a useful
value.

Consider a `write_all` method defined for I/O types by a `Write` protocol:

```python
import typing as t

class Write(t.Protocol) {
    def write_all(self, data: bytes) -> Result[None, WriteError]: ...
}
```

This method doesn't produce a value, but the write may fail. It's crucial to
handle the error case, and not write something like this:

```python
from pathlib import Path

file: Write = File.create("valuable_data.txt").unwrap()
# If `write_all` errors, then we'll never know, because the return value is ignored.
file.write_all(b"important message")
```

You might instead, if you don't want to handle the error, simply assert success
with expect. This will throw an exception if the write fails, providing a marginally useful
message indicating why:

```python
file: Write = File.create("valuable_data.txt").unwrap()
file.write_all(b"important message").expect("failed to write message")
```

You might also simply assert success:

```python
assert file.write_all(b"important message").is_ok()


# or bubble up the error
def write_message() -> Result[None, WriteError]:
    file: Write = File.create("valuable_data.txt").unwrap()

    return file.write_all(b"important message").map(lambda _: None)
```
"""

from __future__ import annotations

import contextlib
import functools
from collections.abc import Awaitable, Callable
from typing import (
    Any,
    Generic,
    TypeAlias,
    TypeVar,
    cast,
)

# main result generics bounnd to classes
T = TypeVar("T", covariant=True)
E = TypeVar("E", covariant=True)


# free result generics used in methods
U = TypeVar("U")
F = TypeVar("F")

# non-result generics used in methods
A = TypeVar("A")
R = TypeVar("R")


class UnwrapError(AssertionError):
    """Raised when the asserted state of a `Result`/`ResultAsync` is not met.

    Do not catch this error.
    """

    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self) -> str:
        return self.msg

    def __repr__(self) -> str:
        return f"UnwrapError({self.msg})"


@functools.total_ordering
class Ok(Generic[T, E]):
    """Ok variant of Result."""

    __slots__ = ("_value",)
    __match_args__ = ("_value",)

    _value: T

    def __init__(self, value: T):
        self._value = value

    def is_ok(self) -> bool:
        """Returns `true` if the result is `Ok`.

        ## Examples

        ```python
        >>> x = Ok(-3)
        >>> x.is_ok()
        True

        >>> x = Err("Some error message")
        >>> x.is_ok()
        False

        ```
        """
        return True

    def is_ok_and(self, func: Callable[[T], bool]) -> bool:
        """Returns `True` if the result is `Ok` and the value inside of it
        matches a predicate.

        ## Examples

        ```python
        >>> x: Result[int, str] = Ok(2)
        >>> x.is_ok_and(lambda y: y > 1)
        True

        >>> x: Result[int, str] = Ok(0)
        >>> x.is_ok_and(lambda y: y > 1)
        False

        >>> x: Result[int, str] = Err("hey")
        >>> x.is_ok_and(lambda y: y > 1)
        False

        ```
        """
        return func(self._value)

    def is_err(self) -> bool:
        """Returns `True` if the result is `Err`.

        ## Examples

        ```python
        >>> x: Result[int, str] = Ok(-3)
        >>> x.is_err()
        False

        >>> x: Result[int, str] = Err("Some error message")
        >>> x.is_err()
        True

        ```
        """
        return False

    def is_err_and(self, func: Callable[[E], bool]) -> bool:
        """Returns `True` if the result is `Err` and the value inside of it
        matches a predicate.

        ## Examples

        ```python
        >>> class NotFound(Exception): ...
        >>> x: Result[int, Exception] = Err(NotFound())
        >>> x.is_err_and(lambda y: isinstance(y, NotFound))
        True

        >>> class PermissionDenied(Exception): ...
        >>> x: Result[int, Exception] = Err(PermissionDenied())
        >>> x.is_err_and(lambda y: isinstance(y, NotFound))
        False

        >>> x: Result[u32, Exception] = Ok(123)
        >>> x.is_err_and(lambda y: isinstance(y, NotFound))
        False

        ```
        """
        return False

    def ok(self) -> T | None:
        """Converts from `Result[T, E]` to `Optional[T]`.

        ## Examples

        ```python
        >>> x: Result[int, str] = Ok(2)
        >>> x.ok()
        2

        >>> x: Result[int, str] = Err("Nothing here")
        >>> repr(x.ok())
        'None'

        ```
        """
        return self._value

    def err(self) -> E | None:
        """Converts from `Result[T, E]` to `Optional[E]`.

        ## Examples

        ```python
        >>> x: Result[int, str] = Ok(2)
        >>> repr(x.err())
        'None'

        >>> x: Result[int, str] = Err('Nothing here')
        >>> x.err()
        'Nothing here'

        ```
        """
        return None

    def map(self, func: Callable[[T], U]) -> Ok[U, E]:
        """Maps a `Result[T, E]` to `Result[U, E]` by applying a function to a
        contained `Ok` value, leaving an `Err` value untouched. `func` cannot
        raise an exception.

        This function can be used to compose the results of two functions.

        ## Exceptions

        Raises `UnwrapError` if `func` raises an exception.

        ## Examples

        ```python
        >>> lines = '1\\n2\\n3\\n4\\n'
        >>> for num in lines.split('\\n'):
        ...     match try_except(lambda: int(num)).map(lambda n: n * 2):
        ...         case Ok(n): print(n)
        ...         case Err(): pass
        ...
        2
        4
        6
        8

        ```
        """
        try:
            return Ok(func(self._value))
        except Exception as e:
            raise UnwrapError(f"{e!r}") from e

    def map_or(self, default: U, func: Callable[[T], U]) -> U:
        """Returns the provided default (if `Err`), or applies a function to the
        contained value (if `Ok`).

        Arguments passed to `map_or` are eagerly evaluated; if you are passing the result of a function call, it is recommended to use `map_or_else`, which is lazily evaluated.

        ## Examples

        ```python
        >>> x: Result[int, str] = Ok(1)
        >>> x.map_or(42, lambda v: v * 2)
        2

        >>> x: Result[int, str] = Err("bar")
        >>> x.map_or(42, lambda v: v * 2)
        42

        ```
        """
        return func(self._value)

    def map_or_else(self, default: Callable[[E], U], func: Callable[[T], U]) -> U:
        """Maps a `Result[T, E]` to `U` by applying fallback function `default`
        to a contained `Err` value, or function `func` to a contained `Ok`
        value.

        ## Examples

        This function can be used to unpack a successful result while handling an error.

        ```python
        >>> k = 21

        >>> x: Result[int, str] = Ok("foo")
        >>> x.map_or_else(lambda e: k * 2, lambda v: len(v))
        3

        >>> x: Result[int, str] = Err("bar")
        >>> x.map_or_else(lambda e: k * 2, lambda v: len(v))
        42

        ```
        """
        return func(self._value)

    def map_err(self, func: Callable[[E], F]) -> Ok[T, F]:
        """Maps a `Result[T, E]` to `Result[T, F]` by applying a function to a
        contained `Err` value, leaving an `Ok` value untouched.

        This function can be used to pass through a successful result while handling an error.

        ```python
        >>> def stringify(x: int) -> str:
        ...     return f"error code: {x}"

        >>> x: Result[int, int] = Ok(2)
        >>> x.map_err(stringify)
        Ok(2)

        >>> x: Result[int, int] = Err(13)
        >>> x.map_err(stringify)
        Err('error code: 13')

        ```
        """
        return Ok(self._value)

    def inspect(self, func: Callable[[Result[T, E]], Any]) -> Result[T, E]:
        """Calls a function with the current result.

        Returns the original result.

        ```python
        >>> x = "4"
        >>> (
        ...     try_except(lambda: int(x))
        ...     .inspect(lambda x: print(x))
        ...     .map(lambda x: x ** 3)
        ...     .expect("failed to parse number")
        ... )
        Ok(4)
        64

        ```
        """
        with contextlib.suppress(Exception):
            func(self)
        return self

    def inspect_ok(self, func: Callable[[T], Any]) -> Result[T, E]:
        """Calls a function with the contained value if `Ok`.

        Returns the original result.

        ```python
        >>> x = "4"
        >>> (
        ...     try_except(lambda: int(x))
        ...     .inspect_ok(lambda x: print(x))
        ...     .map(lambda x: x ** 3)
        ...     .expect("failed to parse number")
        ... )
        4
        64

        ```
        """
        with contextlib.suppress(Exception):
            func(self._value)
        return self

    def inspect_err(self, func: Callable[[E], Any]) -> Result[T, E]:
        """Calls a function with a reference to the contained value if Err.

        Returns the original result.

        ```python
        >>> x = "hello"
        >>> (
        ...     try_except(lambda: int(x))
        ...     .inspect_err(lambda x: print(x))
        ... )
        invalid literal for int() with base 10: 'hello'
        Err(ValueError("invalid literal for int() with base 10: 'hello'"))

        ```
        """
        return self

    def expect(self, msg: str) -> T:
        """Returns the contained Ok value.

        Because this function may raise an exception, its use is generally
        discouraged. Instead, prefer to use pattern matching and handle the
        `Err` case explicitly, or call `unwrap_or` or `unwrap_or_else`.

        ## Exceptions

        Raises `UnwrapError` if the value is an `Err`, with a message
        including the passed message, and the content of the `Err`.

        ## Examples

        ```python
        >>> x: Result[int, str] = Err("emergency failure")
        >>> x.expect("Testing expect")
        Traceback (most recent call last):
            ...
        neverraise.result.UnwrapError: Testing expect: 'emergency failure'

        ```

        ## Recommended Message Style

        We recommend that expect messages are used to describe the reason you
        expect the Result should be Ok.

        ```python
        >>> import os
        >>> (
        ...     try_except(lambda: os.environ["IMPORTANT_PATH"])
        ...     .expect("env variable `IMPORTANT_PATH` should be set by `wrapper_script.sh`")
        ... )
        Traceback (most recent call last):
            ...
        neverraise.result.UnwrapError: env variable `IMPORTANT_PATH` should be set by `wrapper_script.sh`: KeyError('IMPORTANT_PATH')

        ```

        Hint: If you're having trouble remembering how to phrase expect error
        messages remember to focus on the word "should" as in "env variable
        should be set by blah" or "the given binary should be available and
        executable by the current user".

        For more detail on expect message styles and the reasoning behind Rust's
        recommendation please refer to the section on
        ["Common Message Styles"](https://doc.rust-lang.org/std/error/index.html#common-message-styles)
        in the
        [std::error](https://doc.rust-lang.org/std/error/index.html)
        module docs.
        """
        return self._value

    def unwrap(self) -> T:
        """Returns the contained Ok value, consuming the self value.

        Because this function may raise an exception, its use is generally
        discouraged. Instead, prefer to use pattern matching and handle the
        `Err` case explicitly, or call `unwrap_or` or `unwrap_or_else`.

        ## Exceptions

        Raises `UnwrapError` if the value is an `Err`, with a panic message
        provided by the `Err`'s value.

        ## Examples

        ```python
        >>> x: Result[int, str] = Ok(2)
        >>> x.unwrap()
        2

        >>> x: Result[int, str] = Err("emergency failure")
        >>> x.unwrap()
        Traceback (most recent call last):
            ...
        neverraise.result.UnwrapError: 'emergency failure'

        ```
        """
        return self._value

    def expect_err(self, msg: str) -> E:
        """Returns the contained Err value.

        ## Exceptions

        Raises `UnwrapError` if the value is an `Ok`, with a message
        including the passed message, and the content of the `Ok`.

        ## Examples

        ```python
        >>> x: Result[int, str] = Ok(10)
        >>> x.expect_err("Testing expect_err")
        Traceback (most recent call last):
            ...
        neverraise.result.UnwrapError: Testing expect_err: 10

        ```
        """
        raise UnwrapError(f"{msg}: {self._value!r}")

    def unwrap_err(self) -> E:
        """Returns the contained Err value, consuming the self value.

        ## Exceptions

        Raises `UnwrapError` if the value is an `Ok`, with a message
        including the content of the `Ok`.

        ## Examples

        ```python
        >>> x: Result[int, str] = Ok(2)
        >>> x.unwrap_err()
        Traceback (most recent call last):
            ...
        neverraise.result.UnwrapError: 2

        >>> x: Result[int, str] = Err("emergency failure")
        >>> x.unwrap_err()
        'emergency failure'

        ```
        """
        raise UnwrapError(f"{self._value!r}")

    def and_(self, res: Result[U, E]) -> Result[U, E]:
        """Returns `res` if the result is `Ok`, otherwise returns the `Err`
        value of `self`.

        Arguments passed to `and_` are eagerly evaluated; if you are passing the
        result of a function call, it is recommended to use `and_then`, which is
        lazily evaluated.

        ## Examples

        ```python
        >>> x: Result[int, str] = Ok(2)
        >>> y: Result[str, str] = Err('late error')
        >>> x.and_(y)
        Err('late error')

        >>> x: Result[int, str] = Err('early error')
        >>> y: Result[str, str] = Ok('foo')
        >>> x.and_(y)
        Err('early error')

        >>> x: Result[int, str] = Err('not a 2')
        >>> y: Result[str, str] = Err('late error')
        >>> x.and_(y)
        Err('not a 2')

        >>> x: Result[int, str] = Ok(2)
        >>> y: Result[str, str] = Ok('different result type')
        >>> x.and_(y)
        Ok('different result type')

        ```
        """
        return res

    def and_then(self, func: Callable[[T], Result[U, F]]) -> Result[U, E | F]:
        """Calls `func` if the result is `Ok`, otherwise returns the `Err` value
        of `self`.

        This function can be used for control flow based on Result values.

        ## Examples

        ```python
        >>> def sq_then_to_string(x: int) -> Result[str, str]:
        ...     squared = x * x
        ...     if squared > 2**31 - 1:  # simulate 32 bit overflow
        ...         return Err("overflowed")
        ...     return Ok(str(squared))

        >>> Ok(2).and_then(sq_then_to_string)
        Ok('4')
        >>> Ok(1_000_000).and_then(sq_then_to_string)
        Err('overflowed')
        >>> Err('not a number').and_then(sq_then_to_string)
        Err('not a number')

        ```

        Often used to chain fallible operations that may return `Err`.

        ```python
        >>> def safe_sqrt(x: int) -> Result[float, str]:
        ...     if x < 0:
        ...         return Err("negative")
        ...     return Ok(x ** 0.5)
        ...
        >>> Ok(4).and_then(safe_sqrt)
        Ok(2.0)
        >>> Ok(4).and_then(safe_sqrt).map(lambda x: x - 10).and_then(safe_sqrt)
        Err('negative')
        >>> Ok(-4).and_then(safe_sqrt)
        Err('negative')
        >>> Err("not a number").and_then(safe_sqrt)
        Err('not a number')

        ```
        """
        return cast("Result[U, E | F]", func(self._value))

    def or_(self, res: Result[T, E]) -> Result[T, E]:
        """Returns res if the result is Err, otherwise returns the Ok value of
        self.

        Arguments passed to `or_` are eagerly evaluated; if you are passing the
        result of a function call, it is recommended to use `or_else`, which is
        lazily evaluated.

        ## Examples

        ```python
        >>> x: Result[int, str] = Ok(2)
        >>> y: Result[int, str] = Err('late error')
        >>> x.or_(y)
        Ok(2)

        >>> x: Result[int, str] = Err('early error')
        >>> y: Result[int, str] = Ok(2)
        >>> x.or_(y)
        Ok(2)

        >>> x: Result[int, str] = Err('not a 2')
        >>> y: Result[int, str] = Err('late error')
        >>> x.or_(y)
        Err('late error')

        >>> x: Result[int, str] = Ok(2)
        >>> y: Result[int, str] = Ok(100)
        >>> x.or_(y)
        Ok(2)

        ```
        """
        return self

    def or_else(self, func: Callable[[E], Result[T, F]]) -> Result[T, F]:
        """Calls `func` if the result is `Err`, otherwise returns the `Ok` value
        of `self`.

        This function can be used for control flow based on result values.

        ## Examples

        ```python
        >>> def sq(x: int) -> Result[int, int]:
        ...     return Ok(x * x)
        >>> def err(x: int) -> Result[int, int]:
        ...     return Err(x)

        >>> Ok(2).or_else(sq).or_else(sq)
        Ok(2)
        >>> Ok(2).or_else(err).or_else(sq)
        Ok(2)
        >>> Err(3).or_else(sq).or_else(err)
        Ok(9)
        >>> Err(3).or_else(err).or_else(err)
        Err(3)

        ```
        """
        return cast("Result[T, F]", self)

    def unwrap_or(self, default: T) -> T:
        """Returns the contained `Ok` value or a provided default.

        Arguments passed to `unwrap_or` are eagerly evaluated; if you are passing the result of a function call, it is recommended to use `unwrap_or_else`, which is lazily evaluated.

        ## Examples

        ```python
        >>> default = 2
        >>> x: Result[int, str] = Ok(9)
        >>> x.unwrap_or(default)
        9

        >>> x: Result[int, str] = Err("error")
        >>> x.unwrap_or(default)
        2

        ```
        """
        return self._value

    def unwrap_or_else(self, func: Callable[[E], T]) -> T:
        """Returns the contained Ok value or computes it from a closure.

        ## Examples

        ```python
        >>> def count(x: str) -> int:
        ...     return len(x)

        >>> Ok(2).unwrap_or_else(count)
        2
        >>> Err("foo").unwrap_or_else(count)
        3

        ```
        """
        return self._value

    def try_except(
        self,
        func: Callable[[T], U],
        error_handler: Callable[[Exception], F] = lambda e: e,
    ) -> Result[U, E | F]:
        try:
            return Ok(func(self._value))
        except Exception as e:
            return Err(error_handler(e))

    def try_except_async(
        self,
        func: Callable[[T], Awaitable[U]],
        error_handler: Callable[[Exception], F],
    ) -> ResultAsync[U, E | F]:
        async def wrapper() -> Result[U, E | F]:
            try:
                return Ok(await func(self._value))
            except Exception as e:
                return Err(error_handler(e))

        return ResultAsync(wrapper())

    def __str__(self) -> str:
        return f"Ok({self._value})"

    def __repr__(self) -> str:
        return f"Ok({self._value!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Ok):
            return False
        other_ok = cast("Ok[Any, Any]", other)
        return self._value == other_ok._value

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Ok):
            other_ok = cast("Ok[Any, Any]", other)
            return self._value < other_ok._value

        if isinstance(other, Err):
            return True

        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)


@functools.total_ordering
class Err(Generic[T, E]):
    """Err variant of Result.

    See `Ok` for documentation.
    """

    # Type casts

    __slots__ = ("_error",)
    __match_args__ = ("_error",)

    _error: E

    def __init__(self, error: E):
        self._error = error

    def is_ok(self) -> bool:
        return False

    def is_ok_and(self, func: Callable[[T], bool]) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def is_err_and(self, func: Callable[[E], bool]) -> bool:
        return func(self._error)

    def ok(self) -> T | None:
        return None

    def err(self) -> E | None:
        return self._error

    def map(self, func: Callable[[T], U]) -> Err[U, E]:
        return Err(self._error)

    def map_or(self, default: U, func: Callable[[T], U]) -> U:
        return default

    def map_or_else(self, default: Callable[[E], U], func: Callable[[T], U]) -> U:
        return default(self._error)

    def map_err(self, func: Callable[[E], F]) -> Err[T, F]:
        return Err(func(self._error))

    def inspect(self, func: Callable[[Result[T, E]], Any]) -> Result[T, E]:
        with contextlib.suppress(Exception):
            func(self)
        return self

    def inspect_ok(self, func: Callable[[T], Any]) -> Result[T, E]:
        return self

    def inspect_err(self, func: Callable[[E], Any]) -> Result[T, E]:
        with contextlib.suppress(Exception):
            func(self._error)
        return self

    def expect(self, msg: str) -> T:
        raise UnwrapError(f"{msg}: {self._error!r}")

    def unwrap(self) -> T:
        raise UnwrapError(f"{self._error!r}")

    def expect_err(self, msg: str) -> E:
        return self._error

    def unwrap_err(self) -> E:
        return self._error

    def and_(self, res: Result[U, E]) -> Result[U, E]:
        return cast("Result[U, E]", self)

    def and_then(self, func: Callable[[T], Result[U, F]]) -> Result[U, E | F]:
        return cast("Result[U, E | F]", self)

    def or_(self, res: Result[T, E]) -> Result[T, E]:
        return res

    def or_else(self, func: Callable[[E], Result[T, F]]) -> Result[T, F]:
        return func(self._error)

    def unwrap_or(self, default: T) -> T:
        return default

    def unwrap_or_else(self, func: Callable[[E], T]) -> T:
        return func(self._error)

    def try_except(
        self,
        func: Callable[[T], U],
        error_handler: Callable[[Exception], F] = lambda e: e,
    ) -> Result[U, E | F]:
        return cast(Result[U, E | F], self)

    def try_except_async(
        self,
        func: Callable[[T], Awaitable[U]],
        error_handler: Callable[[Exception], F],
    ) -> ResultAsync[U, E | F]:
        async def wrapper() -> Result[U, E | F]:
            return cast(Result[U, E | F], self)

        return ResultAsync(wrapper())

    def __str__(self) -> str:
        return f"Err({self._error})"

    def __repr__(self) -> str:
        return f"Err({self._error!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Err):
            return False
        other_err = cast("Err[Any, Any]", other)
        return self._error == other_err._error

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Err):
            other_err = cast("Err[Any, Any]", other)
            return self._error < other_err._error

        if isinstance(other, Ok):
            return False

        return NotImplemented


Result: TypeAlias = Ok[T, E] | Err[T, E]


class ResultAsync(Generic[T, E]):
    __slots__ = ("_coro",)

    _coro: Awaitable[Result[T, E]]

    def __init__(self, coro: Awaitable[Result[T, E]]) -> None:
        self._coro = coro

    @staticmethod
    def from_coro(
        coro: Awaitable[U],
        error_handler: Callable[[Exception], F] = lambda e: e,
    ) -> ResultAsync[U, F]:
        async def wrapper() -> Result[U, F]:
            try:
                return Ok(await coro)
            except Exception as e:
                return Err(error_handler(e))

        return ResultAsync(wrapper())

    def map(self, func: Callable[[T], U]) -> ResultAsync[U, E]:
        async def wrapper() -> Result[U, E]:
            result = await self._coro
            match result:
                case Ok(value):
                    return Ok(func(value))
                case Err(error):
                    return Err(error)

        return ResultAsync(wrapper())

    def map_async(self, func: Callable[[T], Awaitable[U]]) -> ResultAsync[U, E]:
        async def wraper() -> Result[U, E]:
            match await self._coro:
                case Ok(value):
                    return Ok(await func(value))
                case Err(error):
                    return Err(error)

        return ResultAsync(wraper())

    def try_catch(
        self,
        func: Callable[[T], U],
        error_handler: Callable[[Exception], F],
    ) -> ResultAsync[U, E | F]:
        async def wraper() -> Result[U, E | F]:
            match await self._coro:
                case Ok(value):
                    ...
                case Err() as err:
                    return cast("Result[U, E | F]", err)
            try:
                return Ok(func(value))
            except Exception as e:
                return Err(error_handler(e))

        return ResultAsync(wraper())

    def try_catch_async(
        self,
        func: Callable[[T], Awaitable[U]],
        error_handler: Callable[[Exception], F] = lambda e: e,
    ) -> ResultAsync[U, E | F]:
        async def wraper() -> Result[U, E | F]:
            match await self._coro:
                case Ok(value):
                    ...
                case Err() as err:
                    return cast("Result[U, E | F]", err)

            try:
                return Ok(await func(value))
            except Exception as e:
                return Err(error_handler(e))

        return ResultAsync(wraper())

    def __await__(self):
        return self._coro.__await__()

    def inspect(self, func: Callable[[Result[T, E]], Any]) -> ResultAsync[T, E]:
        async def wrapper():
            res = await self._coro
            with contextlib.suppress(Exception):
                func(res)
            return res

        return ResultAsync(wrapper())

    def inspect_ok(self, func: Callable[[T], Any]) -> ResultAsync[T, E]:
        async def wrapper():
            res = await self._coro
            with contextlib.suppress(Exception):
                match res:
                    case Ok(val):
                        func(val)
                    case _:
                        ...
            return res

        return ResultAsync(wrapper())

    def inspect_err(self, func: Callable[[E], Any]) -> ResultAsync[T, E]:
        async def wrapper():
            res = await self._coro
            with contextlib.suppress(Exception):
                match res:
                    case Err(err):
                        func(err)
                    case _:
                        ...
            return res

        return ResultAsync(wrapper())

    def map_err(self, func: Callable[[E], F]) -> ResultAsync[T, F]:
        async def wrapper() -> Result[T, F]:
            match await self._coro:
                case Ok(value):
                    return Ok(value)
                case Err(error):
                    return Err(func(error))

        return ResultAsync(wrapper())

    def map_err_async(self, func: Callable[[E], Awaitable[F]]) -> ResultAsync[T, F]:
        async def wrapper() -> Result[T, F]:
            match await self._coro:
                case Ok(value):
                    return Ok(value)
                case Err(error):
                    return Err(await func(error))

        return ResultAsync(wrapper())

    def and_then(self, func: Callable[[T], ResultAsync[U, F]]) -> ResultAsync[U, E | F]:
        async def wrapper() -> Result[U, E | F]:
            match await self._coro:
                case Ok(value):
                    return await func(value)
                case Err(error):
                    return Err(error)

        return ResultAsync(wrapper())


def ErrAsync(error: E) -> ResultAsync[T, E]:  # type: ignore
    async def wrapper() -> Result[T, E]:
        return Err(error)

    return ResultAsync(wrapper())


def OkAsync(value: T) -> ResultAsync[T, E]:  # type: ignore
    async def wrapper() -> Result[T, E]:
        return Ok(value)

    return ResultAsync(wrapper())


def try_except(
    func: Callable[[], T],
    error_handler: Callable[[Exception], E] = lambda e: e,
) -> Result[T, E]:
    """Create a `Result` from a function that may raise an exception.

    ## Examples

    ```python
    >>> try_except(lambda: 1 / 0)
    Err(ZeroDivisionError('division by zero'))

    ```
    """
    try:
        return Ok(func())
    except Exception as e:
        return Err(error_handler(e))
