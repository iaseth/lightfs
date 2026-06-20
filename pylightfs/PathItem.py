import time
from pathlib import Path

from rich.text import Text
from textual.binding import Binding
from textual.widgets import ListItem, Label, ListView

from .constants import AUDIO_EXTENSIONS



class PathItem(ListItem):
	def __init__(self, path: Path, *args, **kwargs):
		self.path = path
		self.last_click = 0
		if path.is_dir():
			icon = "📁 "
		elif path.suffix.lower() in AUDIO_EXTENSIONS:
			icon = "🎵 "
		else:
			icon = "📄 "

		# Using rich.text.Text prevents UI markup parsing glitches with non-ASCII names
		label_text = Text(f"{icon}{path.name or str(path)}")
		super().__init__(Label(label_text), *args, **kwargs)

	def on_click(self, event) -> None:
		# 1. Stop event so ListView doesn't trigger native behavior
		event.stop()

		# 2. Manually highlight this item on a single click
		list_view = self.parent
		if isinstance(list_view, ListView):
			try:
				list_view.index = list_view.children.index(self)
			except ValueError:
				pass

		# 3. Double-click logic with safe deferred execution
		now = time.time()
		if now - getattr(self, "last_click", 0) < 0.4:
			# Defer execution by 0.05s so UI state resolves before list wipes
			self.set_timer(0.05, lambda: self.app.execute_path(self.path))

		self.last_click = now

