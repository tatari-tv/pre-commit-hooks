import argparse
from os.path import dirname
from unittest.mock import call
from unittest.mock import patch

import pytest

from python_hooks.disallowed_attributes import check_attributes, MESSAGE
from python_hooks.disallowed_attributes import check_attributes
from python_hooks.disallowed_attributes import main
from python_hooks.disallowed_attributes import validate_args
from python_hooks.utills.ignore_check import FunctionCall

FILE = f'{dirname(__file__)}/data/disallowed_sample.py'

@patch('builtins.print')
@patch('python_hooks.disallowed_attributes.ignore_check')
def test_check_attributes(mock_ignore_check, mock_print):
    mock_ignore_check.return_value = [
        FunctionCall('disallowed', 'allowed', 15, 9),
    ]
    actual_return = check_attributes(FILE, ['disallowed'], ['allowed'])

    assert actual_return == 1
    assert mock_ignore_check.call_count == 1
    assert mock_ignore_check.call_args == call(
        FILE,
        [FunctionCall('disallowed', 'allowed', 15, 9),
        FunctionCall('disallowed', 'allowed', 16, 5)],
    )

    mock_print.assert_has_calls(
        [
            call(MESSAGE.format(name='disallowed', filename=FILE, line=15, col_offset=9, replacement='allowed')),
        ]
    )


@patch('builtins.print')
def test_check_function_call_pass(mock_print):
    assert check_attributes(FILE, ['my_function'], ['my_other_function']) == 0
    mock_print.assert_not_called()


def test_call_main_caught():
    args = argparse.Namespace(disallowed_attributes=['split'], replacement_attributes=['splitlines'], file_list=[FILE])
    actual = main(args)
    expected = 1
    assert actual == expected


def test_call_main_pass():
    args = argparse.Namespace(disallowed_attributes=['my_function'], replacement_attributes=['my_other_function'], file_list=[FILE])
    actual = main(args)
    expected = 0
    assert actual == expected


def test_validate_args_caught():
    args = argparse.Namespace(
        disallowed_attributes=['split', 'splat'], replacement_attributes=['splitlines'], file_list=[FILE, FILE]
    )
    with pytest.raises(ValueError) as error:
        validate_args(args)
    assert str(error.value) == "Number of replacements does not match the number to check"
