from textual.widgets import Static
from textual.reactive import reactive



class AudioProgress(Static):
	"""Interactive progress bar for audio playback."""
	progress = reactive(0.0)

	def render(self):
		width = self.size.width
		if width == 0: return ""
		filled = int(width * self.progress)
		return "█" * filled + "━" * (width - filled)

	def on_click(self, event):
		if self.size.width > 0:
			percent = (event.x / self.size.width) * 100
			self.app.seek_absolute(percent)

