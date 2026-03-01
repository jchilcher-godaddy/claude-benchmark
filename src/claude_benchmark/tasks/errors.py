class TaskLoadError(Exception):
    """Raised when a task directory is missing task.toml, has invalid TOML, or references non-existent files."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class TaskValidationError(Exception):
    """Raised when Pydantic schema validation fails."""

    def __init__(self, task_name: str, validation_error):
        self.task_name = task_name
        self.validation_error = validation_error
        error_count = len(validation_error.errors())
        error_details = "\n".join(
            f"  - {err['loc'][0] if err['loc'] else 'root'}: {err['msg']}"
            for err in validation_error.errors()
        )
        self.message = (
            f"Validation failed for task '{task_name}' ({error_count} error(s)):\n{error_details}"
        )
        super().__init__(self.message)
