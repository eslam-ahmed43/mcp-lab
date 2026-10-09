from types import SimpleNamespace

from agent import clean_args, declaration, to_schema
from run_eval import args_match


def kind(schema):
    return getattr(schema.type, "value", schema.type)


def test_optional_string_becomes_plain_string_schema():
    schema = to_schema(
        {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "key"}
    )
    assert kind(schema) == "STRING"
    assert schema.description == "key"


def test_object_schema_keeps_required_fields():
    schema = to_schema(
        {
            "type": "object",
            "properties": {"title": {"type": "string"}, "n": {"type": "integer"}},
            "required": ["title"],
        }
    )
    assert kind(schema) == "OBJECT"
    assert schema.required == ["title"]
    assert kind(schema.properties["n"]) == "INTEGER"


def test_tool_without_arguments_has_no_parameters():
    tool = SimpleNamespace(
        name="list_pending_approvals",
        description="List approvals.",
        input_schema={"type": "object", "properties": {}},
    )
    assert declaration(tool).parameters is None


def test_integral_floats_become_ints():
    assert clean_args({"task_id": 14.0, "ratio": 0.5}) == {"task_id": 14, "ratio": 0.5}
    assert isinstance(clean_args({"task_id": 14.0})["task_id"], int)


def test_args_match_is_case_insensitive_for_text_and_exact_for_numbers():
    assert args_match({"title": "Prepare the demo"}, {"title": "prepare the DEMO now"})
    assert args_match({"task_id": 14}, {"task_id": 14})
    assert not args_match({"task_id": 14}, {"task_id": 13})
    assert not args_match({"priority": "high"}, {"priority": "low"})
