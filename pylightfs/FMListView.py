from textual.binding import Binding
from textual.widgets import ListView

from .PathItem import PathItem



class FMListView(ListView):
	"""Custom ListView that ignores mouse clicks for execution and maps Enter strictly."""
	BINDINGS = [
		Binding("enter", "execute_highlighted", "Open", show=False)
	]

	def action_execute_highlighted(self) -> None:
		item = self.highlighted_child
		if isinstance(item, PathItem):
			self.app.execute_path(item.path)


