"""
Unit tests for uuid_manager
"""

from components.uuid_manager import UuidManager


def test_uuid_manager():
    manager = UuidManager()

    # Add an item and check its UUID
    item = "Test Item"
    item_uuid = manager.add_item(item)
    assert manager.get_uuid(item) == item_uuid

    # Get the item by its UUID
    assert manager.get_item(item_uuid) == item

    # Check if the UUID is unique
    other_item_uuid = manager.add_item("Other Test Item")
    assert other_item_uuid != item_uuid

    # Get the UUID of a non-existent item
    assert manager.get_uuid("xxx") is None

    # Length of the manager should be 2
    assert len(manager) == 2

    manager.clear()

    # Length of the manager should be 0 after clearing
    assert len(manager) == 0