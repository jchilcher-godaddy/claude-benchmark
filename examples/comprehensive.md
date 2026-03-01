# Code Standards

## Style
- Use snake_case for all function and variable names
- Use UPPER_CASE for module-level constants
- Maximum line length: 100 characters
- All functions must have type hints on parameters and return values

## Documentation
- Use Google-style docstrings with Args, Returns, and Raises sections
- Every module must have a module-level docstring
- Include inline comments only for non-obvious logic

## Error Handling
- Raise specific exceptions (ValueError, TypeError) with descriptive messages
- Never use bare except or except Exception
- Validate all function inputs at the boundary

## Logging
- Use the logging module with `logging.getLogger(__name__)`
- Never use print() for debugging or status output
- Log at appropriate levels: DEBUG for internals, INFO for operations, ERROR for failures

## Code Quality
- Define magic numbers as module-level UPPER_CASE constants
- Keep functions under 20 lines
- Prefer early returns to reduce nesting
- No unused imports or variables
