import argparse
from os.path import dirname
from unittest.mock import call
from unittest.mock import patch

import pytest

from python_hooks.utills.ignore_check import IdentifierCheck
from python_hooks.imagetag_branch_constraint import check_file, DISALLOWED_MESSAGE

FILE = f'{dirname(__file__)}/data/imagetag_branch_sample.py'


@patch('python_hooks.imagetag_branch_constraint.ignore_check')
def test_check_file_with_constraints_and_ignore(mock_ignore_check):
    mock_ignore_check.return_value = [
    ]
    actual_return = check_file(FILE)
    assert actual_return == 0
    assert mock_ignore_check.call_count == 1
    assert mock_ignore_check.call_args == call(
        FILE,
        [
            IdentifierCheck('image_tag', None, 29, 4),
            IdentifierCheck('branch', None, 36, 4),
            IdentifierCheck('image_tag', None, 47, 4),
            IdentifierCheck('branch', None, 53, 4),
            IdentifierCheck('image_tag', None, 66, 4),
        ],
    )


@patch('python_hooks.imagetag_branch_constraint.print')
def test_check_file_with_constraints(mock_print):
    actual_return = check_file(FILE)
    assert actual_return == 1
    assert mock_print.call_args_list == [
        call(
            DISALLOWED_MESSAGE.format(
                name='image_tag', filename=FILE, line=29, col_offset=0
            )
        ),
        call(
            DISALLOWED_MESSAGE.format(
                name='branch', filename=FILE, line=36, col_offset=0
            )
        ),
        call(
            DISALLOWED_MESSAGE.format(
                name='image_tag', filename=FILE, line=47, col_offset=0
            )
        ),
        call(
            DISALLOWED_MESSAGE.format(
                name='branch', filename=FILE, line=53, col_offset=0
            )
        ),
        call(
            DISALLOWED_MESSAGE.format(
                name='image_tag', filename=FILE, line=66, col_offset=0
            )
        ),
    ]