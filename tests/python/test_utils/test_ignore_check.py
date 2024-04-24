from python_hooks.utills.ignore_check import FunctionCall
from python_hooks.utills.ignore_check import ignore_check


def test_ignore_check():
    input_check_fails = [
        FunctionCall('split', 'splitlines', 3, 0),
        FunctionCall('split', 'splitlines', 4, 0),
        FunctionCall('split', 'splitlines', 7, 0),  # this line is annotated in the test data file (FILE)
        FunctionCall('disallowed', 'allowed', 15, 9),
        FunctionCall('disallowed', 'allowed', 16, 5), # this line is annotated in the test data file (FILE)
    ]
    expected_annotated_check_fails = [
        FunctionCall('split', 'splitlines', 3, 0),
        FunctionCall('split', 'splitlines', 4, 0),
        FunctionCall('disallowed', 'allowed', 15, 9)
    ]
    filename = 'tests/python/data/disallowed_sample.py'
    assert ignore_check(filename, input_check_fails) == expected_annotated_check_fails
