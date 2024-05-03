import argparse
from os.path import dirname
from unittest.mock import call
from unittest.mock import patch

import pytest

from python_hooks.disallowed_identifiers import check_identifiers
from python_hooks.disallowed_identifiers import DISALLOWED_MESSAGE
from python_hooks.disallowed_identifiers import Identifier
from python_hooks.disallowed_identifiers import main
from python_hooks.disallowed_identifiers import validate_args
from python_hooks.utills.ignore_check import IdentifierCheck

FILE = f'{dirname(__file__)}/data/disallowed_sample.py'


@patch('builtins.print')
@patch('python_hooks.disallowed_identifiers.ignore_check')
def test_check_identifiers_function(mock_ignore_check, mock_print):
    mock_ignore_check.return_value = [
        IdentifierCheck('split', 'splitlines', 2, 0),
        IdentifierCheck('split', 'splitlines', 3, 0),
    ]
    actual_return = check_identifiers(FILE, Identifier.function, ['split'], ['splitlines'])
    assert actual_return == 1
    assert mock_ignore_check.call_count == 1
    assert mock_ignore_check.call_args == call(
        FILE,
        [
            IdentifierCheck('split', 'splitlines', 2, 0),
            IdentifierCheck('split', 'splitlines', 3, 0),
            IdentifierCheck('split', 'splitlines', 6, 0),
            IdentifierCheck('split', 'splitlines', 7, 0),
            IdentifierCheck('split', 'splitlines', 11, 4),
            IdentifierCheck('split', 'splitlines', 7, 0),
            IdentifierCheck('split', 'splitlines', 11, 4),
        ],
    )

    mock_print.assert_has_calls(
        [
            call(
                DISALLOWED_MESSAGE.format(
                    identifier=Identifier.function, name='split', filename=FILE, line=2, col_offset=0, replacement='splitlines'
                )
            ),
            call(
                DISALLOWED_MESSAGE.format(
                    identifier=Identifier.function, name='split', filename=FILE, line=3, col_offset=0, replacement='splitlines'
                )
            ),
        ]
    )


@patch('builtins.print')
@patch('python_hooks.disallowed_identifiers.ignore_check')
def test_check_identifiers_attribute(mock_ignore_check, mock_print):
    mock_ignore_check.return_value = [
        IdentifierCheck('disallowed', 'allowed', 19, 9),
    ]
    actual_return = check_identifiers(FILE, Identifier.attribute, ['disallowed'], ['allowed'])

    assert actual_return == 1
    assert mock_ignore_check.call_count == 1
    assert mock_ignore_check.call_args == call(
        FILE,
        [IdentifierCheck('disallowed', 'allowed', 23, 9), IdentifierCheck('disallowed', 'allowed', 24, 5)],
    )

    mock_print.assert_has_calls(
        [
            call(
                DISALLOWED_MESSAGE.format(
                    identifier=Identifier.attribute, name='disallowed', filename=FILE, line=19, col_offset=9, replacement='allowed'
                )
            ),
        ]
    )


@patch('builtins.print')
def test_check_function_call_pass(mock_print):
    assert check_identifiers(FILE, Identifier.function, ['my_function'], ['my_other_function']) == 0
    mock_print.assert_not_called()


def test_call_main_caught():
    args = argparse.Namespace(identifier=Identifier.function, disallowed=['split'], replacements=['splitlines'], file_list=[FILE])
    actual = main(args)
    expected = 1
    assert actual == expected


def test_call_main_pass():
    args = argparse.Namespace(
        identifier=Identifier.function, disallowed=['my_function'], replacements=['my_other_function'], file_list=[FILE]
    )
    actual = main(args)
    expected = 0
    assert actual == expected


def test_validate_args_caught():
    args = argparse.Namespace(
        identifier=Identifier.function, disallowed=['split', 'splat'], replacements=['splitlines'], file_list=[FILE, FILE]
    )
    with pytest.raises(ValueError) as error:
        validate_args(args)
    assert str(error.value) == "Number of replacements does not match the number to check"
