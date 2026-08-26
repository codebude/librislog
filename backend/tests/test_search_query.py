"""Unit tests for the field-specific search query parser."""

from app.services.search import parse_search_query


def _terms(query: str) -> list[tuple[str | None, str, bool]]:
    return [(t.field, t.value, t.negated) for t in parse_search_query(query)]


def test_parse_unprefixed_only() -> None:
    assert _terms("dune") == [(None, "dune", False)]


def test_parse_single_field() -> None:
    assert _terms("author:Marlen") == [("author", "Marlen", False)]


def test_parse_quoted_multiword() -> None:
    assert _terms('author:"Marlen Haushofer"') == [("author", "Marlen Haushofer", False)]


def test_parse_multiple_fields() -> None:
    assert _terms("author:Dittert title:fragezeichen") == [
        ("author", "Dittert", False),
        ("title", "fragezeichen", False),
    ]


def test_parse_mixed_prefixed_and_unprefixed() -> None:
    assert _terms("fragezeichen author:Dittert") == [
        (None, "fragezeichen", False),
        ("author", "Dittert", False),
    ]


def test_parse_unknown_prefix_kept_in_unprefixed() -> None:
    assert _terms("foo:bar") == [(None, "foo:bar", False)]


def test_parse_unclosed_quote() -> None:
    assert _terms('author:"Marlen') == [("author", "Marlen", False)]


def test_parse_empty_quoted_value() -> None:
    assert _terms('author:""') == []


def test_parse_case_insensitive_prefix() -> None:
    assert _terms("Author:Marlen") == [("author", "Marlen", False)]
    assert _terms("TITLE:dune") == [("title", "dune", False)]


def test_parse_escaped_quote() -> None:
    assert _terms(r'author:"O\"Brian"') == [("author", 'O"Brian', False)]


def test_parse_negated_field_term() -> None:
    assert _terms("-tag:audi") == [("tag", "audi", True)]


def test_parse_negated_quoted_unprefixed() -> None:
    assert _terms('"cars" -"mercedes benz"') == [
        (None, "cars", False),
        (None, "mercedes benz", True),
    ]


def test_parse_negated_single_unprefixed() -> None:
    assert _terms("-cars") == [(None, "cars", True)]


def test_parse_mixed_positive_and_negated() -> None:
    assert _terms("tag:cars -tag:audi") == [
        ("tag", "cars", False),
        ("tag", "audi", True),
    ]


def test_parse_lone_negation() -> None:
    assert _terms("-") == []


def test_parse_bare_prefix() -> None:
    # A bare prefix without a value is treated as literal unprefixed text.
    assert _terms("author:") == [(None, "author:", False)]


def test_parse_all_supported_prefixes() -> None:
    query = "author:a title:t publisher:p tag:g language:en possession:owned notes:n description:d"
    fields = [t.field for t in parse_search_query(query)]
    assert fields == [
        "author",
        "title",
        "publisher",
        "tag",
        "language",
        "possession",
        "notes",
        "description",
    ]


def test_possession_condition_accepts_enum_values() -> None:
    from app.services.search import _possession_condition

    assert _possession_condition("owned") is not None
    assert _possession_condition("digital_access") is not None
    assert _possession_condition("to acquire") is not None
    assert _possession_condition("owned") is not None


def test_possession_condition_rejects_unknown_value() -> None:
    from app.services.search import _possession_condition

    assert _possession_condition("not-a-status") is None