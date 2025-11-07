"""List data business logic - separated from CLI presentation.

This module will contain logic for listing available data.
TODO: Implement in Phase 6
"""

from typing import List
from .models import DataSummary


def execute_list_data() -> List[DataSummary]:
    """
    List available data in the database.

    TODO: Implement data discovery:
    - Query database for available symbols
    - Get date ranges and record counts
    - Calculate data sizes
    - Return structured summaries

    Returns:
        List of DataSummary objects, one per symbol
    """
    raise NotImplementedError("List data command will be implemented in Phase 6")
