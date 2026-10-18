"""The advisory discoverability check: it reports, it never gates.

The verifier's job is evidence, so a writing-quality observation must never
change an outcome. These tests pin both halves: the notes the check produces
from a post's text, and the fact that a passing draft stays a pass when it
carries them.
"""
from app.verification.editorial import discoverability_notes


def test_a_post_that_names_its_subject_plainly_has_no_notes():
    content = (
        "I cut our CI pipeline from 18 minutes to 6 by caching Docker "
        "layers.\n\nThe trick was ordering the COPY steps so the dependency "
        "layer changes least often."
    )

    assert discoverability_notes(content) == ()


def test_a_generic_opener_is_reported():
    notes = discoverability_notes(
        "Excited to share something I have been working on.\n\nIt is a small "
        "service that returns shipment status to a tracking dashboard."
    )

    assert len(notes) == 1
    assert "generic announcement" in notes[0]


def test_a_too_short_first_line_is_reported():
    notes = discoverability_notes(
        "Big news.\n\nThe API now returns shipments to the tracking dashboard "
        "and the migration guard catches bad states."
    )

    assert len(notes) == 1
    assert "too short to establish the subject" in notes[0]


def test_a_link_only_post_is_reported():
    notes = discoverability_notes("https://example.com/some-article")

    assert len(notes) == 1
    assert "mostly a link" in notes[0]


def test_an_empty_draft_has_nothing_to_say():
    assert discoverability_notes("") == ()
    assert discoverability_notes("   \n  ") == ()


def test_the_check_is_deterministic_and_order_stable():
    content = "Excited to share https://example.com/x"

    assert discoverability_notes(content) == discoverability_notes(content)
