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
