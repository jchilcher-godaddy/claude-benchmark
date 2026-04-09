"""Tests for code-gen-05: Configuration deep merge engine."""

import pytest

from config_merge import ConfigMergeError, merge_configs, validate_config


class TestShallowMerge:
    def test_simple_scalar_merge(self):
        result = merge_configs({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_overlay_wins_for_scalars(self):
        result = merge_configs({"a": 1}, {"a": 2})
        assert result == {"a": 2}

    def test_empty_base(self):
        result = merge_configs({}, {"a": 1})
        assert result == {"a": 1}

    def test_empty_overlay(self):
        result = merge_configs({"a": 1}, {})
        assert result == {"a": 1}


class TestDeepMerge:
    def test_nested_dict_merge(self):
        base = {"db": {"host": "localhost", "port": 5432}}
        overlay = {"db": {"port": 3306}}
        result = merge_configs(base, overlay)
        assert result == {"db": {"host": "localhost", "port": 3306}}

    def test_deeply_nested_merge(self):
        base = {"a": {"b": {"c": {"d": 1}}}}
        overlay = {"a": {"b": {"c": {"d": 2, "e": 3}}}}
        result = merge_configs(base, overlay)
        assert result == {"a": {"b": {"c": {"d": 2, "e": 3}}}}

    def test_lists_are_replaced(self):
        base = {"tags": [1, 2, 3]}
        overlay = {"tags": [4, 5]}
        result = merge_configs(base, overlay)
        assert result == {"tags": [4, 5]}


class TestMultipleOverlays:
    def test_three_overlays_precedence(self):
        result = merge_configs({"a": 1}, {"a": 2}, {"a": 3})
        assert result == {"a": 3}

    def test_overlays_accumulate_keys(self):
        result = merge_configs({"a": 1}, {"b": 2}, {"c": 3})
        assert result == {"a": 1, "b": 2, "c": 3}


class TestDeleteSentinel:
    def test_delete_removes_key(self):
        result = merge_configs({"a": 1, "b": 2}, {"a": "__delete__"})
        assert result == {"b": 2}

    def test_delete_nonexistent_key(self):
        result = merge_configs({"a": 1}, {"b": "__delete__"})
        assert result == {"a": 1}

    def test_delete_nested_key(self):
        base = {"db": {"host": "localhost", "port": 5432}}
        overlay = {"db": {"port": "__delete__"}}
        result = merge_configs(base, overlay)
        assert result == {"db": {"host": "localhost"}}


class TestTypeConflicts:
    def test_dict_vs_scalar_raises(self):
        with pytest.raises(ConfigMergeError):
            merge_configs({"a": {"nested": 1}}, {"a": "string"})

    def test_scalar_vs_dict_raises(self):
        with pytest.raises(ConfigMergeError):
            merge_configs({"a": "string"}, {"a": {"nested": 1}})


class TestCircularReferences:
    def test_circular_ref_raises(self):
        a = {}
        a["self"] = a
        with pytest.raises(ConfigMergeError):
            merge_configs(a, {"b": 1})


class TestNoMutation:
    def test_base_not_mutated(self):
        base = {"a": 1, "b": {"c": 2}}
        original_base = {"a": 1, "b": {"c": 2}}
        merge_configs(base, {"a": 99, "b": {"c": 99}})
        assert base == original_base

    def test_overlay_not_mutated(self):
        overlay = {"a": 1}
        original_overlay = {"a": 1}
        merge_configs({"b": 2}, overlay)
        assert overlay == original_overlay


class TestValidateConfig:
    def test_valid_config(self):
        config = {"host": "localhost", "port": 8080}
        schema = {"host": str, "port": int}
        assert validate_config(config, schema) == []

    def test_missing_key(self):
        config = {"host": "localhost"}
        schema = {"host": str, "port": int}
        violations = validate_config(config, schema)
        assert len(violations) == 1
        assert "port" in violations[0].lower() or "port" in violations[0]

    def test_type_mismatch(self):
        config = {"host": "localhost", "port": "not_an_int"}
        schema = {"host": str, "port": int}
        violations = validate_config(config, schema)
        assert len(violations) == 1

    def test_nested_schema_validation(self):
        config = {"db": {"host": "localhost", "port": "bad"}}
        schema = {"db": {"host": str, "port": int}}
        violations = validate_config(config, schema)
        assert len(violations) == 1

    def test_multiple_violations(self):
        config = {"host": 123}
        schema = {"host": str, "port": int}
        violations = validate_config(config, schema)
        assert len(violations) == 2
