"""Small helpers shared by the tests."""

from PySide6.QtCore import QEventLoop, QItemSelectionModel, QTimer


def wait_until(condition, timeout_ms: int = 10000) -> bool:
    """Spins the Qt event loop until `condition()` is true or the timeout passes."""
    if condition():
        return True
    loop = QEventLoop()
    elapsed = 0

    def tick():
        nonlocal elapsed
        elapsed += 20
        if condition() or elapsed >= timeout_ms:
            loop.quit()

    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(tick)
    timer.start()
    loop.exec()
    timer.stop()
    return condition()


def visible_names(window) -> list[str]:
    """Names in the file list, in the order the user sees them."""
    return [window.proxy.index(row, 0).data() for row in range(window.proxy.rowCount())]


def select(window, *names):
    """Selects the rows with the given names in the file list."""
    selection = window.view.selectionModel()
    selection.clearSelection()
    for row in range(window.proxy.rowCount()):
        index = window.proxy.index(row, 0)
        if index.data() in names:
            selection.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
