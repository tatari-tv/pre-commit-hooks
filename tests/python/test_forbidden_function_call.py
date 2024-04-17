import argparse
from os.path import dirname
from unittest.mock import call
from unittest.mock import patch

import pytest

from python_hooks.disallowed_function_calls import check_function_call
from python_hooks.disallowed_function_calls import main
from python_hooks.disallowed_function_calls import MESSAGE
from python_hooks.disallowed_function_calls import validate_args
from python_hooks.utills.ignore_check import FunctionCall

FILE = f'{dirname(__file__)}/data/disallowed_function_calls_sample.py'


@patch('builtins.print')
@patch('python_hooks.disallowed_function_calls.ignore_check')
def test_check_function_call_caught(mock_ignore_check, mock_print):
    mock_ignore_check.return_value = [
        FunctionCall('split', 'splitlines', 2, 0),
        FunctionCall('split', 'splitlines', 3, 0),
    ]
    actual_return = check_function_call(FILE, ['split'], ['splitlines'])
    assert actual_return == 1
    assert mock_ignore_check.call_count == 1
    assert mock_ignore_check.call_args == call(
        FILE,
        [FunctionCall('split', 'splitlines', 2, 0), FunctionCall('split', 'splitlines', 3, 0), FunctionCall('split', 'splitlines', 6, 0)],
    )

    mock_print.assert_has_calls(
        [
            call(MESSAGE.format(name='split', filename=FILE, line=2, col_offset=0, replacement='splitlines')),
            call(MESSAGE.format(name='split', filename=FILE, line=3, col_offset=0, replacement='splitlines')),
        ]
    )


@patch('builtins.print')
def test_check_function_call_pass(mock_print):
    assert check_function_call(FILE, ['my_function'], ['my_other_function']) == 0
    mock_print.assert_not_called()


def test_call_main_caught():
    args = argparse.Namespace(disallowed_function_calls=['split'], replacement_function_calls=['splitlines'], file_list=[FILE])
    actual = main(args)
    expected = 1
    assert actual == expected


def test_call_main_pass():
    args = argparse.Namespace(disallowed_function_calls=['my_function'], replacement_function_calls=['my_other_function'], file_list=[FILE])
    actual = main(args)
    expected = 0
    assert actual == expected


def test_validate_args_caught():
    args = argparse.Namespace(
        disallowed_function_calls=['split', 'splat'], replacement_function_calls=['splitlines'], file_list=[FILE, FILE]
    )
    with pytest.raises(ValueError) as error:
        validate_args(args)
    assert str(error.value) == "Number of replacement functions does not match the number of functions to check"
