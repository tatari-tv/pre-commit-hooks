from python_hooks.utills.ignore_check import FunctionCall
from python_hooks.utills.ignore_check import ignore_check


def test_ignore_check():
    input_check_fails = [
        FunctionCall('split', 'splitlines', 2, 0),
        FunctionCall('split', 'splitlines', 3, 0),
        FunctionCall('split', 'splitlines', 6, 0),  # this line is annotated in the test data file (FILE)
    ]
    expected_annotated_check_fails = [
        FunctionCall('split', 'splitlines', 2, 0),
        FunctionCall('split', 'splitlines', 3, 0),
    ]
    filename = 'tests/python/data/disallowed_function_calls_sample.py'
    assert ignore_check(filename, input_check_fails) == expected_annotated_check_fails
