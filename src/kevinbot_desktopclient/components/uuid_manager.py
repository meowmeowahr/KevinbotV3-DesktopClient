import uuid


class UuidManager:
    def __init__(self):
        # Dictionary to store items and their UUIDs
        self._items = {}

    def add_item(self, item):
        """Add an item to the manager and return its UUID."""
        item_uuid = uuid.uuid4()
        self._items[item_uuid] = item
        return item_uuid

    def get_item(self, item_uuid):
        """Retrieve an item by its UUID."""
        return self._items.get(item_uuid)

    def get_items(self):
        """Retrieve all items managed."""
        return list(self._items.values())

    def get_uuid(self, item):
        """Retrieve the UUID of an item."""
        for uid, stored_item in self._items.items():
            if stored_item == item:
                return uid
        return None

    def clear(self):
        """Clear all items from the manager."""
        self._items.clear()

    def __len__(self):
        """Return the number of items managed."""
        return len(self._items)
