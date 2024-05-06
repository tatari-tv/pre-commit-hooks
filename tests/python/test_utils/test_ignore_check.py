from python_hooks.utills.ignore_check import IdentifierCheck
from python_hooks.utills.ignore_check import ignore_check


def test_ignore_check():
    input_check_fails = [
        IdentifierCheck('split', 'splitlines', 2, 0),
        IdentifierCheck('split', 'splitlines', 3, 0),
        IdentifierCheck('split', 'splitlines', 6, 0),  # this line is annotated in the test data file (FILE)
        IdentifierCheck('split', 'splitlines', 7, 0),  # this line is annotated in the test data file (FILE)
        IdentifierCheck('split', 'splitlines', 7, 0),  # this line is annotated in the test data file (FILE)
        IdentifierCheck('split', 'splitlines', 11, 0),  # this line is annotated in the test data file (FILE)
        IdentifierCheck('split', 'splitlines', 11, 0),  # this line is annotated in the test data file (FILE)
        IdentifierCheck('disallowed', 'allowed', 23, 9),
        IdentifierCheck('disallowed', 'allowed', 24, 5),  # this line is annotated in the test data file (FILE)
    ]
    expected_annotated_check_fails = [
        IdentifierCheck('split', 'splitlines', 2, 0),
        IdentifierCheck('split', 'splitlines', 3, 0),
        IdentifierCheck('disallowed', 'allowed', 23, 9),
    ]
    filename = 'tests/python/data/disallowed_sample.py'
    assert ignore_check(filename, input_check_fails) == expected_annotated_check_fails
