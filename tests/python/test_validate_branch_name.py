from python_hooks.validate_branch_name import validate_branch_name


def test_validate_branch_name():
    branch_names_with_exit_code = [
        ("simplebranch", 0),
        ("UPPER-12345/lower", 0),
        ("lower-12345/UPPER", 0),
        ("ABC-123/with-dash", 0),
        ("ABC-123/with_underscore", 0),
        ("ABC-123/with-dash_and_underscore", 0),
        ("ABC-123/with-dash_and_underscore.and.period", 0),
        (".ABC12345/abcdABC", 1),  # starts with period
        ("-ABC12345/abcdABC", 1),  # starts with hyphen
        ("once_upon_a_time_there_was_a_branch_name_that_told_a_very_long_story", 1),  # over 50 characters
        ("ABC-123/abc&123", 1),  # includes non-allowed symbols
    ]

    for branch, exit_code in branch_names_with_exit_code:
        assert validate_branch_name(branch) == exit_code
