from neverraise import Err, Ok, Result


def print_divide(a: int, b: int) -> Result[None, ZeroDivisionError]:
    if b == 0:
        return Err(ZeroDivisionError())
    print(a / b)
    return Ok(None)


def main():
    _ = print_divide(1, 0)  # lint error if pyright "reportUnusedCallResult" is enabled


if __name__ == "__main__":
    main()
