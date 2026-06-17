import time
from pathlib import Path

from rich.text import Text
from textual.binding import Binding
from textual.widgets import ListItem, Label

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
		# Double-click threshold (0.4s) to execute path
		now = time.time()
		if now - getattr(self, "last_click", 0) < 0.4:
			self.app.execute_path(self.path)
		self.last_click = now

