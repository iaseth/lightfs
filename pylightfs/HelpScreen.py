from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Label
from textual.screen import ModalScreen



class HelpScreen(ModalScreen):
	"""A dialog showing keybindings, triggered by 'h'."""

	BINDINGS = [
		Binding("escape", "dismiss", "Dismiss"),
		Binding("h", "dismiss", "Dismiss")
	]

	def compose(self) -> ComposeResult:
		with Vertical(id="help_dialog"):
			yield Label("=== LightFS Keybindings ===", id="help_title")
			yield Label("Navigation:")
			yield Label("  Left/Right : Switch panes")
			yield Label("  Up/Down    : Select items")
			yield Label("  Enter / 2xClick : Open dir/audio")
			yield Label("  u          : Go up one dir")
			yield Label("  .          : Toggle hidden items")
			yield Label("Tabs & Bookmarks:")
			yield Label("  t          : New tab")
			yield Label("  z / Z      : Close tab / Close others")
			yield Label("  o / p      : Prev / Next tab")
			yield Label("  1-9, 0     : Select tab (0 = last)")
			yield Label("  b          : Toggle bookmark")
			yield Label("  S / s      : Set Global Start / Go to Start")
			yield Label("Audio Player:")
			yield Label("  Space / x  : Play/Pause / Stop")
			yield Label("  m          : Toggle Mute")
			yield Label("  [ / ]      : Seek -1m / +1m")
			yield Label("  { / }      : Seek -5m / +5m")
			yield Label("  - / + (=)  : Volume -5% / +5%")
			yield Label("\nPress Esc or h to close.")

	def action_dismiss(self) -> None:
		self.app.pop_screen()


