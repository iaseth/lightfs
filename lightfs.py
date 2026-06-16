import subprocess
import json
from pathlib import Path
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, TabbedContent, TabPane, ListView, ListItem, Label

def get_filtered_paths(directory: Path, show_hidden: bool):
	"""Filters out dotfiles if hidden, then sorts dirs first, then files."""
	try:
		paths = directory.iterdir()
		if not show_hidden:
			paths = (p for p in paths if not p.name.startswith('.'))
		return sorted(paths, key=lambda x: (not x.is_dir(), x.name.lower()))
	except PermissionError:
		return []

class PathItem(ListItem):
	"""Custom ListItem that stores the underlying Path object."""
	def __init__(self, path: Path, *args, **kwargs):
		self.path = path
		if path.is_dir():
			icon = "📁 "
		elif path.suffix.lower() in ['.mp3', '.m4a', '.m4b']:
			icon = "🎵 "
		else:
			icon = "📄 "
			
		super().__init__(Label(f"{icon}{path.name or str(path)}"), *args, **kwargs)

class FMTab(TabPane):
	"""A single Tab representing a directory state."""
	
	def __init__(self, title: str, start_dir: Path, current_dir: Path, *args, **kwargs):
		super().__init__(title, *args, **kwargs)
		self.start_dir = start_dir
		self.current_dir = current_dir

	def compose(self) -> ComposeResult:
		with Horizontal():
			yield ListView(id="p1")
			yield ListView(id="p2")
			yield ListView(id="p3")

	def on_mount(self) -> None:
		self.populate_bookmarks()
		self.refresh_p2()
		# Safely grab focus once the tab's DOM is fully built
		self.query_one("#p2", ListView).focus()

	def populate_bookmarks(self) -> None:
		p1 = self.query_one("#p1", ListView)
		p1.clear()
		for bm in self.app.bookmarks:
			p1.append(PathItem(bm))

	def refresh_p2(self) -> None:
		"""Populates p2 with current_dir items, filtering hidden if needed."""
		p2 = self.query_one("#p2", ListView)
		p2.clear()
		
		for p in get_filtered_paths(self.current_dir, self.app.show_hidden):
			p2.append(PathItem(p))

	def refresh_p3(self, target_dir: Path) -> None:
		"""Populates p3 with the contents of the directory highlighted in p2."""
		p3 = self.query_one("#p3", ListView)
		p3.clear()
		
		for p in get_filtered_paths(target_dir, self.app.show_hidden):
			p3.append(PathItem(p))

	def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
		"""Triggered when scrolling through items in a pane."""
		if event.list_view.id == "p2":
			item = event.item
			if isinstance(item, PathItem) and item.path.is_dir():
				self.refresh_p3(item.path)
			else:
				self.query_one("#p3", ListView).clear()

	def on_list_view_selected(self, event: ListView.Selected) -> None:
		"""Triggered when Enter is pressed on an item."""
		item = event.item
		if not isinstance(item, PathItem):
			return

		target_path = item.path

		if target_path.is_dir():
			# Pressing enter on ANY dir makes it the new current_dir
			self.current_dir = target_path
			self.refresh_p2()
			self.query_one("#p2", ListView).focus()
		else:
			self.app.open_file(target_path)


class LightFS(App):
	"""The main lightweight file manager application."""
	
	TITLE = "LightFS"
	CSS = """
	Horizontal {
		height: 1fr;
	}
	ListView {
		height: 1fr;
		border: solid #444;
		background: $surface;
		padding: 0 1;
	}
	ListView:focus {
		border: double $accent;
	}
	#p1 { width: 25%; }
	#p2 { width: 25%; }
	#p3 { width: 50%; }
	"""

	BINDINGS = [
		Binding("t", "new_tab", "New Tab"),
		Binding("z", "close_tab", "Close Tab"),
		Binding("Z", "close_other_tabs", "Close Others"),
		Binding("1", "first_tab", "First Tab"),
		Binding("0", "last_tab", "Last Tab"),
		Binding("pageup", "prev_tab", "Prev Tab"),
		Binding("pagedown", "next_tab", "Next Tab"),
		Binding("left", "focus_left", "Focus Left"),
		Binding("right", "focus_right", "Focus Right"),
		Binding("u", "go_up", "Go Up"),
		Binding("b", "toggle_bookmark", "Bookmark"),
		Binding("h", "toggle_hidden", "Toggle Hidden"),
		Binding("s", "set_home", "Set Home"),
		Binding("q", "quit", "Quit"),
	]

	def __init__(self):
		super().__init__()
		self.audio_process = None
		self.tab_counter = 0
		self.max_tabs = 99
		self.show_hidden = False
		self.config_file = Path.home() / ".config" / "lightfs" / "config.json"
		self.bookmarks = [
			Path.home(),
			Path.home() / "Music",
			Path.home() / "Downloads",
		]

	def compose(self) -> ComposeResult:
		yield TabbedContent()
		yield Footer()

	def load_config(self) -> list:
		"""Loads application state from JSON."""
		if self.config_file.exists():
			try:
				with open(self.config_file, "r") as f:
					data = json.load(f)
					
				# Load bookmarks ensuring they actually still exist on disk
				saved_bms = data.get("bookmarks", [])
				if saved_bms:
					self.bookmarks = [Path(p) for p in saved_bms if Path(p).exists()]
					
				return data.get("tabs", [])
			except Exception:
				pass
		return []

	def save_config(self) -> None:
		"""Saves application state to JSON."""
		self.config_file.parent.mkdir(parents=True, exist_ok=True)
		
		tabs_data = []
		for tab in self.query(FMTab):
			tabs_data.append({
				"start_dir": str(tab.start_dir),
				"current_dir": str(tab.current_dir)
			})
			
		data = {
			"bookmarks": [str(b) for b in self.bookmarks],
			"tabs": tabs_data
		}
		
		try:
			with open(self.config_file, "w") as f:
				json.dump(data, f, indent=4)
		except Exception:
			pass

	def on_mount(self) -> None:
		tabs_data = self.load_config()
		
		tc = self.query_one(TabbedContent)
		if tabs_data:
			for t in tabs_data:
				self.tab_counter += 1
				tab_id = f"tab-{self.tab_counter}"
				
				# Graceful fallback if saved paths were deleted
				s_dir = Path(t.get("start_dir", Path.home()))
				c_dir = Path(t.get("current_dir", Path.home()))
				if not s_dir.exists(): s_dir = Path.home()
				if not c_dir.exists(): c_dir = Path.home()
				
				new_tab = FMTab(f"{self.tab_counter:02d}", s_dir, c_dir, id=tab_id)
				tc.add_pane(new_tab)
		else:
			self.action_new_tab()

	def on_unmount(self) -> None:
		"""Automatically saves config and kills audio before the app tears down."""
		self.save_config()
		if self.audio_process and self.audio_process.poll() is None:
			self.audio_process.terminate()

	def action_new_tab(self) -> None:
		tc = self.query_one(TabbedContent)
		if tc.tab_count < self.max_tabs:
			self.tab_counter += 1
			new_tab_id = f"tab-{self.tab_counter}"
			new_tab = FMTab(f"{self.tab_counter:02d}", Path.home(), Path.home(), id=new_tab_id)
			tc.add_pane(new_tab)
			tc.active = new_tab_id
		else:
			self.notify(f"Max tabs ({self.max_tabs}) reached!", severity="warning")

	def action_close_tab(self) -> None:
		tc = self.query_one(TabbedContent)
		if tc.tab_count > 1:
			tc.remove_pane(tc.active)
		else:
			self.notify("Cannot close the last tab.", severity="warning")

	def action_close_other_tabs(self) -> None:
		tc = self.query_one(TabbedContent)
		active_id = tc.active
		for tab in tc.query(TabPane):
			if tab.id != active_id:
				tc.remove_pane(tab.id)

	def action_first_tab(self) -> None:
		tc = self.query_one(TabbedContent)
		tabs = list(tc.query(TabPane))
		if tabs:
			tc.active = tabs[0].id

	def action_last_tab(self) -> None:
		tc = self.query_one(TabbedContent)
		tabs = list(tc.query(TabPane))
		if tabs:
			tc.active = tabs[-1].id

	def action_prev_tab(self) -> None:
		self.cycle_tabs(-1)

	def action_next_tab(self) -> None:
		self.cycle_tabs(1)

	def cycle_tabs(self, direction: int) -> None:
		tc = self.query_one(TabbedContent)
		tabs = list(tc.query(TabPane))
		if not tabs: 
			return
			
		current_active = tc.active
		for i, tab in enumerate(tabs):
			if tab.id == current_active:
				next_index = (i + direction) % len(tabs)
				tc.active = tabs[next_index].id
				break

	def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
		"""Ensure p2 gets focus when switching back to an existing tab."""
		try:
			event.pane.query_one("#p2", ListView).focus()
		except Exception:
			pass

	def action_focus_left(self) -> None:
		self.move_pane_focus(-1)

	def action_focus_right(self) -> None:
		self.move_pane_focus(1)

	def move_pane_focus(self, direction: int) -> None:
		tc = self.query_one(TabbedContent)
		active_tab = tc.active_pane
		if not active_tab: 
			return
			
		panes = list(active_tab.query(ListView))
		if not panes: 
			return
			
		try:
			current_idx = panes.index(self.focused)
			next_idx = (current_idx + direction) % len(panes)
			panes[next_idx].focus()
		except ValueError:
			panes[1].focus()

	def action_go_up(self) -> None:
		"""Navigate up one directory level."""
		tc = self.query_one(TabbedContent)
		tab = tc.active_pane
		if isinstance(tab, FMTab):
			tab.current_dir = tab.current_dir.parent
			tab.refresh_p2()
			tab.query_one("#p2", ListView).focus()

	def action_toggle_hidden(self) -> None:
		"""Toggles the visibility of dotfiles and refreshes the current tab."""
		self.show_hidden = not self.show_hidden
		self.notify(f"Hidden files: {'Shown' if self.show_hidden else 'Hidden'}")
		
		tc = self.query_one(TabbedContent)
		tab = tc.active_pane
		if isinstance(tab, FMTab):
			tab.refresh_p2()
			if len(tab.query_one("#p2", ListView).children) == 0:
				tab.query_one("#p3", ListView).clear()

	def action_set_home(self) -> None:
		"""Sets the tab's start_dir to the current directory."""
		tc = self.query_one(TabbedContent)
		tab = tc.active_pane
		if isinstance(tab, FMTab) and tab.query_one("#p2").has_focus:
			tab.start_dir = tab.current_dir
			self.notify(f"Tab start dir set to: {tab.start_dir}")

	def action_toggle_bookmark(self) -> None:
		"""Adds or removes directories from bookmarks based on pane focus."""
		focused = self.focused
		if not isinstance(focused, ListView):
			return
			
		item = focused.highlighted_child
		if not isinstance(item, PathItem):
			return
			
		target_path = item.path
		
		if focused.id == "p1":
			if target_path in self.bookmarks:
				self.bookmarks.remove(target_path)
				self.refresh_all_bookmarks()
				self.notify(f"Removed bookmark: {target_path.name}")
		elif focused.id in ("p2", "p3"):
			if target_path.is_dir() and target_path not in self.bookmarks:
				self.bookmarks.append(target_path)
				self.refresh_all_bookmarks()
				self.notify(f"Added bookmark: {target_path.name}")

	def refresh_all_bookmarks(self) -> None:
		"""Updates p1 across all tabs when a bookmark changes."""
		for tab in self.query(FMTab):
			tab.populate_bookmarks()

	def open_file(self, path: Path) -> None:
		if path.suffix.lower() in ['.mp3', '.m4a', '.m4b']:
			if self.audio_process and self.audio_process.poll() is None:
				self.audio_process.terminate()
				self.audio_process.wait()
				
			self.audio_process = subprocess.Popen(
				["mpv", "--no-video", str(path)],
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL
			)
			self.notify(f"Playing: {path.name}")
		else:
			subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			self.notify(f"Opened: {path.name}")

if __name__ == "__main__":
	app = LightFS()
	app.run()