"""The safe manual metrics import: parse everything, write nothing on a mistake.

The importer is the only path metrics take into the store, so its safety
properties are the point: a bad file imports nothing, an unknown publication
imports nothing, and the default is a dry run.
"""
import pytest

from app.metrics.import_metrics import (
    ImportPlan,
    MetricRow,
    apply_plan,
    main,
    parse_metrics_csv,
)
from app.state import StateStore


@pytest.fixture
def store(tmp_path):
    with StateStore(tmp_path / "metrics.db") as state:
        yield state


def _publication(store, post_id):
    run = store.start_run("branding")
    intent = store.create_publish_intent(run.run_id, f"post {post_id}")
    return store.record_publication(
        intent.intent_id, "published", linkedin_post_id=post_id)


HEADER = ("publication_id,age_hours,impressions,reactions,comments,"
          "reposts,source\n")


def test_a_valid_file_parses_into_rows():
    plan = parse_metrics_csv(
        HEADER + "pub_a,6,1000,10,4,1,manual\npub_a,168,5000,40,20,3,manual\n"
    )

    assert plan.ok
    assert plan.rows == (
        MetricRow("pub_a", 6.0, 1000, 10, 4, 1, "manual"),
        MetricRow("pub_a", 168.0, 5000, 40, 20, 3, "manual"),
    )


def test_optional_columns_default_to_zero():
    plan = parse_metrics_csv("publication_id,age_hours\npub_a,6\n")

    assert plan.ok
    assert plan.rows[0].impressions == 0
    assert plan.rows[0].source == "manual"


def test_a_missing_required_column_is_an_error_with_no_rows():
    plan = parse_metrics_csv("publication_id\npub_a\n")

    assert not plan.ok
    assert plan.rows == ()
    assert "age_hours" in plan.errors[0]


def test_an_unknown_column_is_an_error():
    plan = parse_metrics_csv(
        "publication_id,age_hours,impressions,reactions,comments,reposts,"
        "source,extra\npub_a,6,1,1,1,1,manual,x\n"
    )

    assert not plan.ok
    assert "unknown column" in plan.errors[0]


def test_a_row_with_too_many_columns_is_an_error():
    plan = parse_metrics_csv(HEADER + "pub_a,6,1,1,1,1,manual,extra\n")

    assert not plan.ok
    assert "too many columns" in plan.errors[0]


def test_a_bad_number_fails_the_whole_file():
    plan = parse_metrics_csv(
        HEADER + "pub_a,6,1000,10,4,1,manual\npub_b,seven,1,1,1,1,manual\n"
    )

    assert not plan.ok
    assert plan.rows == ()
    assert "line 3" in plan.errors[0]
    assert "age_hours" in plan.errors[0]


def test_a_negative_count_fails_the_whole_file():
    plan = parse_metrics_csv(HEADER + "pub_a,6,-1,0,0,0,manual\n")

    assert not plan.ok
    assert "non-negative" in plan.errors[0]


def test_an_empty_file_is_an_error():
    assert not parse_metrics_csv("").ok
    assert not parse_metrics_csv(HEADER).ok


def test_applying_a_plan_with_errors_is_refused():
    plan = ImportPlan(errors=("line 2: bad",))

    with pytest.raises(ValueError):
        apply_plan(object(), plan)


def test_applying_a_plan_with_an_unknown_publication_writes_nothing(store):
    known = _publication(store, "urn:li:share:known")
    plan = parse_metrics_csv(
        HEADER + f"{known.publication_id},6,100,1,1,1,manual\n"
        "pub_missing,6,100,1,1,1,manual\n"
    )

    with pytest.raises(ValueError):
        apply_plan(store, plan)

    assert store.list_publication_metrics() == []


def test_applying_a_valid_plan_records_every_row(store):
    publication = _publication(store, "urn:li:share:known")
    plan = parse_metrics_csv(
        HEADER + f"{publication.publication_id},6,100,1,1,1,manual\n"
        f"{publication.publication_id},168,900,9,9,9,manual\n"
    )

    recorded = apply_plan(store, plan)

    assert recorded == 2
    assert len(store.list_publication_metrics(publication.publication_id)) == 2


def test_applying_a_plan_can_override_the_source(store):
    publication = _publication(store, "urn:li:share:known")
    plan = parse_metrics_csv(
        HEADER + f"{publication.publication_id},6,100,1,1,1,manual\n"
    )

    apply_plan(store, plan, source="export-2026-10")

    metric = store.list_publication_metrics(publication.publication_id)[0]
    assert metric.source == "export-2026-10"


def test_the_cli_defaults_to_a_dry_run(store, tmp_path):
    publication = _publication(store, "urn:li:share:known")
    csv_path = tmp_path / "metrics.csv"
    csv_path.write_text(
        HEADER + f"{publication.publication_id},6,100,1,1,1,manual\n",
        encoding="utf-8",
    )

    exit_code = main([str(csv_path), "--database", str(store.path)])

    assert exit_code == 0, "a valid file exits cleanly even in dry run"
    assert store.list_publication_metrics() == [], "dry run writes nothing"


def test_the_cli_applies_when_asked(store, tmp_path):
    publication = _publication(store, "urn:li:share:known")
    csv_path = tmp_path / "metrics.csv"
    csv_path.write_text(
        HEADER + f"{publication.publication_id},6,100,1,1,1,manual\n",
        encoding="utf-8",
    )

    exit_code = main([str(csv_path), "--apply", "--database", str(store.path)])

    assert exit_code == 0
    assert len(store.list_publication_metrics()) == 1


def test_the_cli_refuses_a_broken_file(tmp_path):
    csv_path = tmp_path / "metrics.csv"
    csv_path.write_text(HEADER + "pub_a,not-a-number,0,0,0,0,manual\n",
                        encoding="utf-8")

    assert main([str(csv_path)]) == 2
