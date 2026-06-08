from qgis.PyQt.QtCore import (
    Qt,
    QAbstractItemModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
)


class TreeNode:
    """
    Internal data structure for FeatureTypeTreeModel
    """

    def __init__(
        self, display_text: str, feature_type: str, parent: "TreeNode|None" = None
    ):
        self._display_text: str = display_text
        self._feature_type: str = feature_type
        self._parent: TreeNode | None = parent
        self._children: list[TreeNode] = []

    def append_child(self, child: "TreeNode"):
        self._children.append(child)

    def child(self, row: int) -> "TreeNode|None":
        if 0 <= row < len(self._children):
            return self._children[row]
        return None

    def child_count(self) -> int:
        return len(self._children)

    def column_count(self) -> int:
        return 1

    def display_text(self) -> str:
        return self._display_text

    def feature_type(self) -> str:
        return self._feature_type

    def parent_feature_type(self) -> str:
        parent: TreeNode = self
        # want parents all the way UP to but EXCLUDING the root node (which
        # has no parent itself)
        while parent.parent() and parent.parent().parent():
            parent = parent.parent()

        return parent.feature_type()

    def parent(self) -> "TreeNode|None":
        return self._parent

    def row(self) -> int:
        if self._parent:
            return self._parent._children.index(self)
        return 0


class FeatureTypeTreeModel(QAbstractItemModel):
    """
    A model which shows the feature type hierarchy in a tree
    """

    FEATURE_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1
    PARENT_FEATURE_TYPE_ROLE = Qt.ItemDataRole.UserRole + 2

    def __init__(self, data_list, parent: QObject | None = None):
        super().__init__(parent)
        self.root_item = TreeNode("Root", feature_type="")
        self.set_types(data_list)

    def set_types(self, data_list):
        for item in data_list:
            self.add_types(item)

    def add_types(self, types: str | dict[str, list[str]]):
        if isinstance(types, str):
            feature_type = types
            node = TreeNode(
                display_text=feature_type,
                feature_type=feature_type,
                parent=self.root_item,
            )
            row = self.root_item.child_count()
            self.beginInsertRows(QModelIndex(), row, row)
            self.root_item.append_child(node)
            self.endInsertRows()
        elif isinstance(types, dict):
            for key, values in types.items():
                key_node = TreeNode(
                    display_text=key, feature_type=key, parent=self.root_item
                )
                if isinstance(values, list):
                    for val in values:
                        val_node = TreeNode(
                            display_text=(val), feature_type=(val), parent=key_node
                        )
                        key_node.append_child(val_node)
                row = self.root_item.child_count()
                self.beginInsertRows(QModelIndex(), row, row)
                self.root_item.append_child(key_node)
                self.endInsertRows()

    def remove_types(self, types: str | dict[str, list[str]]):
        root_feature_types = []
        if isinstance(types, str):
            root_feature_types.append(types)
        else:
            for key, values in types.items():
                root_feature_types.append(key)

        for feature_type in root_feature_types:
            for row, child in enumerate(self.root_item._children):
                if child.feature_type() == feature_type:
                    self.beginRemoveRows(QModelIndex(), row, row)
                    del self.root_item._children[row]
                    self.endRemoveRows()
                    continue

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        child_item = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index: QModelIndex):
        if not index.isValid():
            return QModelIndex()

        child_item = index.internalPointer()
        parent_item = child_item.parent()

        if parent_item == self.root_item or parent_item is None:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent: QModelIndex = QModelIndex()):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        return parent_item.child_count()

    def columnCount(self, parent: QModelIndex = QModelIndex()):
        if parent.isValid():
            return parent.internalPointer().column_count()
        return self.root_item.column_count()

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        flags = super().flags(index)
        if self.hasChildren(index):
            flags &= ~Qt.ItemFlag.ItemIsSelectable

        return flags

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            item: TreeNode = index.internalPointer()
            return item.display_text()
        elif role == self.FEATURE_TYPE_ROLE:
            item: TreeNode = index.internalPointer()
            return item.feature_type()
        elif role == self.PARENT_FEATURE_TYPE_ROLE:
            item: TreeNode = index.internalPointer()
            return item.parent_feature_type()
        return None


class FeatureTypeFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text: str | None = None

        self.setRecursiveFilteringEnabled(True)
        self.sort(0)
        self.setDynamicSortFilter(True)

    def set_filter_text(self, filter_text: str | None):
        self._filter_text = filter_text
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._filter_text:
            return True

        source_index = self.sourceModel().index(source_row, 0, source_parent)
        item_text = self.sourceModel().data(source_index, Qt.ItemDataRole.DisplayRole)

        if not item_text:
            return False

        if self._filter_text in item_text.lower():
            return True

        return False
