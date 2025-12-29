from app.services.universal_mapper import UniversalMapper


def test_mapper_generic_extra():
    data = {"foo": "bar", "baz": 123}
    mapper = UniversalMapper("UNKNOWN")
    pd = mapper.map(data)
    assert pd.extra.get("foo") == "bar"
    assert pd.extra.get("baz") == 123
