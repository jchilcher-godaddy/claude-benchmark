class ConfigMergeError(Exception):
    """Raised when a configuration merge fails."""


def merge_configs(base, *overlays):
    """Deep-merge configuration dicts. Later overlays take precedence."""

    def _check_circular(d, seen=None):
        if seen is None:
            seen = set()
        if id(d) in seen:
            raise ConfigMergeError("Circular reference detected")
        seen.add(id(d))
        for v in d.values():
            if isinstance(v, dict):
                _check_circular(v, seen)

    def _merge(a, b, path=""):
        result = dict(a)
        for key, b_val in b.items():
            current_path = f"{path}.{key}" if path else key

            if b_val == "__delete__":
                result.pop(key, None)
                continue

            if key in result:
                a_val = result[key]
                a_is_dict = isinstance(a_val, dict)
                b_is_dict = isinstance(b_val, dict)

                if a_is_dict and b_is_dict:
                    result[key] = _merge(a_val, b_val, current_path)
                elif a_is_dict != b_is_dict:
                    raise ConfigMergeError(
                        f"Type conflict at {current_path!r}: "
                        f"cannot merge {type(a_val).__name__} with {type(b_val).__name__}"
                    )
                else:
                    result[key] = b_val
            else:
                result[key] = b_val

        return result

    _check_circular(base)
    for overlay in overlays:
        _check_circular(overlay)

    result = dict(base)
    for overlay in overlays:
        result = _merge(result, overlay)
    return result


def validate_config(merged, schema, path=""):
    """Validate a merged config against a schema. Return list of violation strings."""
    violations = []

    for key, expected in schema.items():
        current_path = f"{path}.{key}" if path else key

        if key not in merged:
            violations.append(f"Missing required key: {current_path!r}")
            continue

        actual = merged[key]
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                violations.append(
                    f"Type mismatch at {current_path!r}: "
                    f"expected dict, got {type(actual).__name__}"
                )
            else:
                violations.extend(validate_config(actual, expected, current_path))
        else:
            if not isinstance(actual, expected):
                violations.append(
                    f"Type mismatch at {current_path!r}: "
                    f"expected {expected.__name__}, got {type(actual).__name__}"
                )

    return violations
