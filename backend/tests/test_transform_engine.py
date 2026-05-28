"""Unit tests for the transform engine."""

import pytest

from app.services import transform_engine as te


class TestValidateTransform:
    def test_empty_code_returns_error(self) -> None:
        assert te.validate_transform("") == ["Transform code is empty"]
        assert te.validate_transform("   ") == ["Transform code is empty"]

    def test_valid_expression(self) -> None:
        errors = te.validate_transform("value.strip().lower()")
        assert errors == []

    def test_valid_multiline(self) -> None:
        code = """\
match = re.search(r'\\d{4}', value)
if match:
    return match.group(0)
return ''
"""
        errors = te.validate_transform(code)
        assert errors == []

    def test_forbidden_import(self) -> None:
        errors = te.validate_transform("import os")
        assert any("Forbidden import" in e for e in errors)

    def test_forbidden_exec(self) -> None:
        errors = te.validate_transform("exec('print(1)')")
        assert len(errors) > 0

    def test_forbidden_eval(self) -> None:
        errors = te.validate_transform("eval('1+1')")
        assert len(errors) > 0

    def test_forbidden_open(self) -> None:
        errors = te.validate_transform("open('/etc/passwd')")
        assert len(errors) > 0

    def test_forbidden_function_def(self) -> None:
        errors = te.validate_transform("def foo(): pass")
        assert any("FunctionDef" in e for e in errors)

    def test_forbidden_class_def(self) -> None:
        errors = te.validate_transform("class Foo: pass")
        assert any("ClassDef" in e for e in errors)

    def test_forbidden_with(self) -> None:
        errors = te.validate_transform("with open('x') as f: pass")
        assert any("With" in e for e in errors)

    def test_forbidden_try(self) -> None:
        errors = te.validate_transform("try:\n    pass\nexcept:\n    pass")
        assert any("Try" in e for e in errors)

    def test_forbidden_lambda(self) -> None:
        errors = te.validate_transform("(lambda x: x)(1)")
        assert any("Lambda" in e for e in errors)

    def test_syntax_error(self) -> None:
        errors = te.validate_transform("value.strip(")
        assert any("Syntax error" in e for e in errors)


class TestCompileTransform:
    def test_simple_expression(self) -> None:
        fn = te.compile_transform("return value.upper()")
        result = te.execute_transform(fn, "hello", {}, {})
        assert result == "HELLO"

    def test_multiline_with_if(self) -> None:
        code = """\
match = re.search(r'\\d{4}', value)
if match:
    return match.group(0)
return ''
"""
        fn = te.compile_transform(code)
        result = te.execute_transform(fn, "Published 2024", {}, {})
        assert result == "2024"

    def test_access_to_datetime(self) -> None:
        # datetime is already available in globals; no import needed
        code = """\
dt = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
return dt.date().isoformat()
"""
        fn = te.compile_transform(code)
        result = te.execute_transform(fn, "2024-01-15T10:30:00", {}, {})
        assert result == "2024-01-15"

    def test_access_to_math(self) -> None:
        code = "return str(math.ceil(float(value)))"
        fn = te.compile_transform(code)
        result = te.execute_transform(fn, "3.14", {}, {})
        assert result == "4"

    def test_row_access(self) -> None:
        code = "return value + ' by ' + row.get('Author', '')"
        fn = te.compile_transform(code)
        result = te.execute_transform(fn, "Dune", {"Author": "Herbert"}, {})
        assert result == "Dune by Herbert"

    def test_context_access(self) -> None:
        code = "return str(context.get('row_number', 0))"
        fn = te.compile_transform(code)
        result = te.execute_transform(fn, "x", {}, {"row_number": 42})
        assert result == "42"

    def test_empty_code_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            te.compile_transform("")

    def test_rejected_import_raises(self) -> None:
        with pytest.raises(ValueError):
            te.compile_transform("import os")


class TestExecuteTransform:
    def test_none_return_becomes_empty_string(self) -> None:
        fn = te.compile_transform("return None")
        result = te.execute_transform(fn, "x", {}, {})
        assert result == ""

    def test_int_return_becomes_string(self) -> None:
        fn = te.compile_transform("return 42")
        result = te.execute_transform(fn, "x", {}, {})
        assert result == "42"

    def test_bool_return_becomes_string(self) -> None:
        fn = te.compile_transform("return True")
        result = te.execute_transform(fn, "x", {}, {})
        assert result == "True"

    def test_list_return_becomes_string(self) -> None:
        fn = te.compile_transform("return [1, 2, 3]")
        result = te.execute_transform(fn, "x", {}, {})
        assert result == "[1, 2, 3]"

    def test_no_return_statement(self) -> None:
        fn = te.compile_transform("x = value.strip()")
        result = te.execute_transform(fn, "  hello  ", {}, {})
        # Function without explicit return returns None, coerced to ""
        assert result == ""


class TestSecurity:
    def test_cannot_import_os(self) -> None:
        with pytest.raises(ValueError):
            te.compile_transform("import os")

    def test_cannot_import_sys(self) -> None:
        with pytest.raises(ValueError):
            te.compile_transform("import sys")

    def test_cannot_use_eval(self) -> None:
        with pytest.raises(ValueError):
            te.compile_transform("eval('1+1')")

    def test_cannot_use_exec(self) -> None:
        with pytest.raises(ValueError):
            te.compile_transform("exec('print(1)')")

    def test_cannot_open_file(self) -> None:
        with pytest.raises(ValueError):
            te.compile_transform("open('/etc/passwd')")

    def test_cannot_access_dunder(self) -> None:
        with pytest.raises((ValueError, SyntaxError)):
            te.compile_transform("return value.__class__")

    def test_cannot_use_yield(self) -> None:
        with pytest.raises(ValueError):
            te.compile_transform("yield value")
