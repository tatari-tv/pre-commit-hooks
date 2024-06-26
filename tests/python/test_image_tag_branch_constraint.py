from os.path import dirname
from unittest.mock import call
from unittest.mock import patch

from python_hooks.image_tag_branch_constraint import check_file
from python_hooks.image_tag_branch_constraint import DISALLOWED_MESSAGE
from python_hooks.utills.ignore_check import IdentifierCheck

FILE = f'{dirname(__file__)}/data/image_tag_branch_sample.py'


@patch('python_hooks.image_tag_branch_constraint.ignore_check')
def test_check_file_with_constraints_and_ignore(mock_ignore_check):
    mock_ignore_check.return_value = []
    actual_return = check_file(FILE)
    assert actual_return == 0
    assert mock_ignore_check.call_count == 1
    assert mock_ignore_check.call_args == call(
        FILE,
        [
            IdentifierCheck('image_tag', None, 19, 99),
            IdentifierCheck('branch', None, 22, 93),
            IdentifierCheck('image_tag', None, 29, 59),
            IdentifierCheck('branch', None, 29, 84),
        ],
    )


@patch('python_hooks.image_tag_branch_constraint.print')
def test_check_file_with_constraints(mock_print):
    actual_return = check_file(FILE)
    assert actual_return == 1
    assert mock_print.call_args_list == [
        call(DISALLOWED_MESSAGE.format(name='image_tag', filename=FILE, line=19, col_offset=99)),
        call(DISALLOWED_MESSAGE.format(name='branch', filename=FILE, line=22, col_offset=93)),
        call(DISALLOWED_MESSAGE.format(name='image_tag', filename=FILE, line=29, col_offset=59)),
        call(DISALLOWED_MESSAGE.format(name='branch', filename=FILE, line=29, col_offset=84)),
    ]
