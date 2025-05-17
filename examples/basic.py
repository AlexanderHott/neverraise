from neverraise import Err, Ok, Result


def divide(a: int, b: int) -> Result[float, ZeroDivisionError]:
    if b == 0:
        return Err(ZeroDivisionError())
    return Ok(a / b)


def square(x: float) -> float:
    return x * x


def main():
    res = divide(1, 0)
    assert res.is_err()

    res2 = divide(1, 0).unwrap_or(float("inf"))
    assert res2 == float("inf")

    res3 = divide(1, 0).map(square).map(lambda x: x * x)
    assert res3.is_err()

    res4 = divide(1, 0).map_err(lambda _: ValueError()).map(square).map(lambda x: x * x)
    assert res4.is_err()


if __name__ == "__main__":
    main()
