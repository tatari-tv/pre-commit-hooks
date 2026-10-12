from python_hooks.marketplace import anchors

DASH = chr(0x2014)


def _run(tmp_path, text, name='doc.md'):
    (tmp_path / name).write_text(text, encoding='utf-8')
    errors = []
    anchors.check_anchors(tmp_path, [name], errors)
    return errors


def test_valid_anchor_passes(tmp_path):
    assert _run(tmp_path, '# Setup Steps\n\nSee [it](#setup-steps).\n') == []


def test_dangling_anchor_is_flagged_with_line(tmp_path):
    errors = _run(tmp_path, '# Setup\n\nSee [it](#missing).\n')
    assert len(errors) == 1
    assert 'doc.md:3' in errors[0]
    assert '#missing' in errors[0]


def test_slug_keeps_one_hyphen_per_space():
    assert anchors.slugify(f'a {DASH} b') == 'a--b'
    assert anchors.slugify('a: b') == 'a-b'


def test_reworded_heading_breaks_old_link(tmp_path):
    errors = _run(tmp_path, '# a: b\n\nSee [it](#a--b).\n')
    assert len(errors) == 1


def test_numeric_suffix_matches_base_slug(tmp_path):
    text = '# Notes\n\n# Notes\n\nSee [it](#notes-1).\n'
    assert _run(tmp_path, text) == []


def test_links_inside_fences_are_ignored(tmp_path):
    text = '# Top\n\n```\n[x](#gone)\n```\n'
    assert _run(tmp_path, text) == []


def test_file_without_headings_is_skipped(tmp_path):
    assert _run(tmp_path, 'no headings [x](#gone)\n') == []


def test_non_markdown_is_skipped(tmp_path):
    assert _run(tmp_path, '# T\n[x](#gone)\n', name='doc.txt') == []


def test_cross_file_links_are_ignored(tmp_path):
    assert _run(tmp_path, '# T\n\n[x](other.md#gone)\n') == []


def test_tilde_fence_hides_links(tmp_path):
    assert _run(tmp_path, '# Top\n\n~~~\n[x](#gone)\n~~~\n') == []


def test_inline_code_hides_links(tmp_path):
    assert _run(tmp_path, '# Top\n\nWrite `[x](#gone)` as an example.\n') == []


def test_shorter_closer_does_not_end_fence(tmp_path):
    text = '# Top\n\n````\n```\n[x](#gone)\n````\n'
    assert _run(tmp_path, text) == []


def test_other_marker_does_not_end_fence(tmp_path):
    text = '# Top\n\n```\n~~~\n[x](#gone)\n```\n'
    assert _run(tmp_path, text) == []


def test_link_after_fence_is_still_checked(tmp_path):
    errors = _run(tmp_path, '# Top\n\n```\ncode\n```\n\n[x](#gone)\n')
    assert len(errors) == 1
    assert 'doc.md:7' in errors[0]


def test_inline_code_in_heading_keeps_its_slug(tmp_path):
    assert _run(tmp_path, '# `run`: it\n\n[x](#run-it)\n') == []


def test_emphasis_markers_do_not_enter_slug(tmp_path):
    assert anchors.slugify('_Setup_') == 'setup'
    assert _run(tmp_path, '# _Setup_\n\n[x](#setup)\n') == []


def test_intraword_underscore_is_kept():
    assert anchors.slugify('snake_case name') == 'snake_case-name'


def test_unknown_numeric_suffix_is_flagged(tmp_path):
    assert len(_run(tmp_path, '# Notes\n\nSee [it](#notes-999).\n')) == 1


def test_second_duplicate_heading_has_suffix_one(tmp_path):
    assert _run(tmp_path, '# Notes\n\n# Notes\n\n[a](#notes) [b](#notes-1)\n') == []
    assert len(_run(tmp_path, '# Notes\n\n# Notes\n\n[c](#notes-2)\n')) == 1
