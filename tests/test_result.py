from typing import Never
from neverraise import Ok, Err, Result

def divide(a: int, b: int) -> Result[float, ZeroDivisionError]:
    if b == 0:
        return Err(ZeroDivisionError())

    return Ok(a / b)


def test_basic():
    assert Ok(1).is_ok()
    assert Ok(1).is_err() is False
    assert Err(ZeroDivisionError()).is_ok() is False
    assert Err(ZeroDivisionError()).is_err() is True



def test_map():
    assert divide(1, 2).map(lambda x: x * 4) == Ok(2)

    match divide(1, 0).map(lambda x: x * 4):
        case Ok():
            assert False
        # case Err(ZeroDivisionError() as e):
        #     assert isinstance(e, ZeroDivisionError)
        case Err(ZeroDivisionError()):
            ...

class SpecialZeroDivisionError(ZeroDivisionError):
    ...

def test_map_err():
    match divide(1, 0).map_err(lambda e: SpecialZeroDivisionError(e)):
        case Ok():
            assert False
        case Err(e):
            assert isinstance(e, SpecialZeroDivisionError)

    match divide(1, 2).map_err(lambda e: SpecialZeroDivisionError(e)):
        case Ok(x):
            assert x == 0.5
        case Err(e):
            assert False

def square(x: float) -> Result[float, Never]:
    return Ok(x * x)

def test_and_then():
    match divide(1, 2).and_then(square):
        case Ok(x):
            assert x == 0.25
        case Err(_):
            assert False

