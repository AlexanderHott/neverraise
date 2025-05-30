# `neverraise`

A mix of Rust's Result type and the neverthrow typescript library.

```python
from neverraise import Result, Ok, Err


def divide(a: int, b: int) -> Result[float, ZeroDivisionError]:
    if b == 0:
        return Err(ZeroDivisionError())
    return Ok(a / b)

match divide(1, 0):
    case Ok(res): print(f"Got {res}")
    case Err(): print("Couldn't divide")
```

```python
def get_todos() -> ResultAsync[list[Todo], HTTPError | JsonParseError | DecodeError]:
    client = httpx.AsyncClient()
    return (
        ResultAsync.from_coro(
            client.get("https://jsonplaceholder.typicode.com/todos/"),
            lambda e: HTTPError(e),
        )
        .try_catch(lambda response: response.json(), lambda e: JsonParseError(e))
        .try_catch(
            lambda json: msgspec.convert(json, type=list[Todo]),
            lambda e: DecodeError(e),
        )
    )
```

> [!IMPORTANT]
> Functions that return `neverraise.Result` or `neverraise.ResultAsync` do not throw exceptions, apart from

- `UnwrapError` caused by calling
  - `map` when the mapping function throws (use `.try_catch` for map operations that can fail)
  - `unwrap`, `expect`, `unwrap_err`, or `expect_err` when called on a non-matching variant of `Result` (e.g. `Err("oh no").unwrap()`)
- Any subclass of `BaseException` such as `asyncio.CancelledError`.

Do not catch `UnwrapError`, as they are not expected to be raised. If one is raised, it means that the code is incorrect. It should be treated as a failed assertion.
