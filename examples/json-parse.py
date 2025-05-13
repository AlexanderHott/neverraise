from neverraise import ResultAsync, Ok, Err
import httpx
import asyncio
import msgspec


class Todo(msgspec.Struct, rename="camel"):
    user_id: int
    id: int
    title: str
    completed: bool


class HTTPError(Exception): ...


class JsonParseError(Exception): ...


class DecodeError(Exception): ...


def get_todos() -> ResultAsync[list[Todo], HTTPError | JsonParseError | DecodeError]:
    client = httpx.AsyncClient()
    return (
        ResultAsync.from_coro(
            client.get("https://jsonplaceholder.typicode.com/todos/"),
            lambda e: HTTPError(e),
        )
        .and_through(lambda response: response.json(), lambda e: JsonParseError(e))
        .and_through(
            lambda json: msgspec.convert(json, type=list[Todo]),
            lambda e: DecodeError(e),
        )
    )


async def main():
    match await get_todos():
        case Ok(todos):
            ...
        case Err(HTTPError() as e):
            print(f"Error fetching todos: {e}, will retry... (todo)")
            return
        case Err() as e:
            print(f"Error {e!r}")
            return

    for i in range(min(len(todos), 10)):
        print(todos[i])


if __name__ == "__main__":
    asyncio.run(main())
