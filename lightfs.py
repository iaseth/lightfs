import subprocess
import json
import socket
from pathlib import Path
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import TabbedContent, TabPane, ListView, ListItem, Label, Static
from textual.screen import ModalScreen
from textual.reactive import reactive

SOCKET_PATH = "/tmp/lightfs_mpv.sock"

def send_mpv_cmd(cmd_list):
	"""Sends JSON IPC commands to the running mpv socket."""
	try:
		with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
			s.connect(SOCKET_PATH)
			s.sendall((json.dumps({"command": cmd_list}) + "\n").encode())
			f = s.makefile()
			return json.loads(f.readline())
	except Exception:
		return None

def format_time(seconds):
	if seconds is None:
		return "00:00"
	m, s = divmod(int(seconds), 60)
	return f"{m:02d}:{s:02d}"

def get_filtered_paths(directory: Path, show_hidden: bool):
	try:
		paths = directory.iterdir()
		if not show_hidden:
			paths = (p for p in paths if not p.name.startswith('.'))
		return sorted(paths, key=lambda x: (not x.is_dir(), x.name.lower()))
	except PermissionError:
		return []


class AudioProgress(Static):
	"""Interactive progress bar for audio playback."""
	progress = reactive(0.0)

	def render(self):
		width = self.size.width
		if width == 0: return ""
		filled = int(width * self.progress)
		return "█" * filled + "━" * (width - filled)

	def on_click(self, event):
		"""Skip to position when the progress bar is clicked."""
		if self.size.width > 0:
			percent = (event.x / self.size.width) * 100
			self.app.seek_absolute(percent)


class HelpScreen(ModalScreen):
	"""A dialog showing keybindings, triggered by 'h'."""
	
	BINDINGS = [Binding("escape", "dismiss", "Dismiss"), Binding("h", "dismiss", "Dismiss")]

	def compose(self) -> ComposeResult:
		with Vertical(id="help_dialog"):
			yield Label("=== LightFS Keybindings ===", id="help_title")
			yield Label("Navigation:")
			yield Label("  Left/Right : Switch panes")
			yield Label("  Up/Down    : Select items")
			yield Label("  Enter      : Open dir/audio")
			yield Label("  u          : Go up one dir")
			yield Label("  .          : Toggle hidden items")
			yield Label("Tabs & Bookmarks:")
			yield Label("  t          : New tab")
			yield Label("  z / Z      : Close tab / Close others")
			yield Label("  PgUp/PgDn  : Prev / Next tab")
			yield Label("  1 / 0      : First / Last tab")
			yield Label("  b / s      : Toggle bookmark / Set start dir")
			yield Label("Audio Player:")
			yield Label("  Space / x  : Play/Pause / Stop")
			yield Label("  m          : Toggle Mute")
			yield Label("  [ / ]      : Seek -1m / +1m")
			yield Label("  { / }      : Seek -5m / +5m")
			yield Label("  - / + (=)  : Volume -5% / +5%")
			yield Label("\nPress Esc or h to close.")

	def action_dismiss(self) -> None:
		self.app.pop_screen()


class PathItem(ListItem):
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
		self.query_one("#p2", ListView).focus()

	def populate_bookmarks(self) -> None:
		p1 = self.query_one("#p1", ListView)
		p1.clear()
		for bm in self.app.bookmarks:
			p1.append(PathItem(bm))

	def refresh_p2(self) -> None:
		p2 = self.query_one("#p2", ListView)
		p2.clear()
		for p in get_filtered_paths(self.current_dir, self.app.show_hidden):
			p2.append(PathItem(p))

	def refresh_p3(self, target_dir: Path) -> None:
		p3 = self.query_one("#p3", ListView)
		p3.clear()
		for p in get_filtered_paths(target_dir, self.app.show_hidden):
			p3.append(PathItem(p))

	def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
		if event.list_view.id == "p2":
			item = event.item
			if isinstance(item, PathItem) and item.path.is_dir():
				self.refresh_p3(item.path)
			else:
				self.query_one("#p3", ListView).clear()

	def on_list_view_selected(self, event: ListView.Selected) -> None:
		item = event.item
		if not isinstance(item, PathItem): return
		target_path = item.path

		if target_path.is_dir():
			self.current_dir = target_path
			self.refresh_p2()
			self.query_one("#p2", ListView).focus()
		else:
			self.app.open_file(target_path)


class LightFS(App):
	TITLE = "LightFS"
	CSS = """
	Horizontal { height: 1fr; }
	ListView {
		height: 1fr;
		border: solid #444;
		background: $surface;
		padding: 0 1;
	}
	ListView:focus { border: double $accent; }
	#p1 { width: 25%; }
	#p2 { width: 25%; }
	#p3 { width: 50%; }
	
	#player_container {
		dock: bottom;
		height: 2;
		background: $surface;
	}
	#audio_filename {
		width: 100%;
		text-align: center;
		background: $panel;
	}
	#audio_progress {
		width: 100%;
		color: $accent;
	}
	#help_dialog {
		width: 40;
		height: auto;
		padding: 1 2;
		background: $surface;
		border: thick $accent;
		align: center middle;
	}
	#help_title { text-align: center; text-style: bold; margin-bottom: 1;}
	HelpScreen { align: center middle; }
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
		Binding(".", "toggle_hidden", "Toggle Hidden"),
		Binding("s", "set_home", "Set Home"),
		Binding("h", "show_help", "Help"),
		Binding("space", "toggle_play", "Play/Pause"),
		Binding("x", "stop_audio", "Stop Audio"),
		Binding("m", "toggle_mute", "Mute"),
		Binding("[", "seek_m60", "Seek -1m"),
		Binding("]", "seek_60", "Seek +1m"),
		Binding("{", "seek_m300", "Seek -5m"),
		Binding("}", "seek_300", "Seek +5m"),
		Binding("-", "vol_down", "Vol -5%"),
		Binding("+", "vol_up", "Vol +5%"),
		Binding("=", "vol_up", "Vol +5%"),
		Binding("q", "quit", "Quit"),
	]

	def __init__(self):
		super().__init__()
		self.audio_process = None
		self.current_track = ""
		self.volume = 100
		self.tab_counter = 0
		self.max_tabs = 99
		self.show_hidden = False
		self.config_file = Path.home() / ".config" / "lightfs" / "config.json"
		self.bookmarks = [Path.home(), Path.home() / "Music", Path.home() / "Downloads"]

	def compose(self) -> ComposeResult:
		yield TabbedContent()
		with Vertical(id="player_container"):
			yield Label("No audio playing", id="audio_filename")
			yield AudioProgress(id="audio_progress")

	def on_mount(self) -> None:
		self.set_interval(1.0, self.update_player_ui)
		self.load_and_restore()

	def load_and_restore(self) -> None:
		tabs_data = []
		active_tab_id = None
		if self.config_file.exists():
			try:
				with open(self.config_file, "r") as f:
					data = json.load(f)
				saved_bms = data.get("bookmarks", [])
				if saved_bms:
					self.bookmarks = [Path(p) for p in saved_bms if Path(p).exists()]
				tabs_data = data.get("tabs", [])
				active_tab_id = data.get("active_tab")
			except Exception:
				pass
		
		tc = self.query_one(TabbedContent)
		if tabs_data:
			for t in tabs_data:
				self.tab_counter += 1
				tab_id = f"tab-{self.tab_counter}"
				s_dir = Path(t.get("start_dir", Path.home()))
				c_dir = Path(t.get("current_dir", Path.home()))
				if not s_dir.exists(): s_dir = Path.home()
				if not c_dir.exists(): c_dir = Path.home()
				
				new_tab = FMTab(f"{self.tab_counter:02d}", s_dir, c_dir, id=tab_id)
				tc.add_pane(new_tab)
				
			if active_tab_id:
				try:
					tc.active = active_tab_id
				except Exception:
					pass
		else:
			self.action_new_tab()

	def save_config(self) -> None:
		self.config_file.parent.mkdir(parents=True, exist_ok=True)
		tabs_data = []
		active_tab = None
		
		# Safely query active tab before UI tears down
		try:
			tc = self.query_one(TabbedContent)
			active_tab = tc.active
		except Exception:
			pass
		
		for tab in self.query(FMTab):
			tabs_data.append({
				"start_dir": str(tab.start_dir),
				"current_dir": str(tab.current_dir)
			})
			
		data = {
			"active_tab": active_tab,
			"bookmarks": [str(b) for b in self.bookmarks],
			"tabs": tabs_data
		}
		try:
			with open(self.config_file, "w") as f:
				json.dump(data, f, indent=4)
		except Exception:
			pass

	def update_player_ui(self) -> None:
		"""Query MPV for time and update the bottom 2 lines."""
		if not self.audio_process or self.audio_process.poll() is not None:
			self.query_one("#audio_filename", Label).update("No audio playing")
			self.query_one("#audio_progress", AudioProgress).progress = 0.0
			return

		pos_resp = send_mpv_cmd(["get_property", "time-pos"])
		dur_resp = send_mpv_cmd(["get_property", "duration"])

		if pos_resp and dur_resp and 'data' in pos_resp and 'data' in dur_resp:
			pos = pos_resp['data']
			dur = dur_resp['data']
			
			if dur > 0:
				self.query_one("#audio_progress", AudioProgress).progress = pos / dur
				self.query_one("#audio_filename", Label).update(
					f"🎵 {self.current_track}   [{format_time(pos)} / {format_time(dur)}]   Vol: {self.volume}%"
				)

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
		if tabs: tc.active = tabs[0].id

	def action_last_tab(self) -> None:
		tc = self.query_one(TabbedContent)
		tabs = list(tc.query(TabPane))
		if tabs: tc.active = tabs[-1].id

	def action_prev_tab(self) -> None:
		self.cycle_tabs(-1)

	def action_next_tab(self) -> None:
		self.cycle_tabs(1)

	def cycle_tabs(self, direction: int) -> None:
		tc = self.query_one(TabbedContent)
		tabs = list(tc.query(TabPane))
		if not tabs: return
		current_active = tc.active
		for i, tab in enumerate(tabs):
			if tab.id == current_active:
				next_index = (i + direction) % len(tabs)
				tc.active = tabs[next_index].id
				break

	def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
		try: event.pane.query_one("#p2", ListView).focus()
		except Exception: pass

	def action_focus_left(self) -> None: self.move_pane_focus(-1)
	def action_focus_right(self) -> None: self.move_pane_focus(1)

	def move_pane_focus(self, direction: int) -> None:
		tc = self.query_one(TabbedContent)
		active_tab = tc.active_pane
		if not active_tab: return
		panes = list(active_tab.query(ListView))
		if not panes: return
		try:
			current_idx = panes.index(self.focused)
			next_idx = (current_idx + direction) % len(panes)
			panes[next_idx].focus()
		except ValueError:
			panes[1].focus()

	def action_go_up(self) -> None:
		tc = self.query_one(TabbedContent)
		tab = tc.active_pane
		if isinstance(tab, FMTab):
			tab.current_dir = tab.current_dir.parent
			tab.refresh_p2()
			tab.query_one("#p2", ListView).focus()

	def action_toggle_hidden(self) -> None:
		self.show_hidden = not self.show_hidden
		self.notify(f"Hidden files: {'Shown' if self.show_hidden else 'Hidden'}")
		tc = self.query_one(TabbedContent)
		tab = tc.active_pane
		if isinstance(tab, FMTab):
			tab.refresh_p2()
			if len(tab.query_one("#p2", ListView).children) == 0:
				tab.query_one("#p3", ListView).clear()

	def action_set_home(self) -> None:
		tc = self.query_one(TabbedContent)
		tab = tc.active_pane
		if isinstance(tab, FMTab) and tab.query_one("#p2").has_focus:
			tab.start_dir = tab.current_dir
			self.notify(f"Tab start dir set to: {tab.start_dir}")

	def action_toggle_bookmark(self) -> None:
		focused = self.focused
		if not isinstance(focused, ListView): return
		item = focused.highlighted_child
		if not isinstance(item, PathItem): return
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
		for tab in self.query(FMTab):
			tab.populate_bookmarks()

	def action_show_help(self) -> None:
		self.push_screen(HelpScreen())

	def open_file(self, path: Path) -> None:
		if path.suffix.lower() in ['.mp3', '.m4a', '.m4b']:
			if self.audio_process and self.audio_process.poll() is None:
				self.audio_process.terminate()
				self.audio_process.wait()
				
			self.audio_process = subprocess.Popen(
				["mpv", "--no-video", f"--input-ipc-server={SOCKET_PATH}", str(path)],
				stdin=subprocess.DEVNULL,
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL
			)
			self.current_track = path.name
			send_mpv_cmd(["set_property", "volume", self.volume])
		else:
			subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			self.notify(f"Opened: {path.name}")

	def action_toggle_play(self) -> None:
		send_mpv_cmd(["cycle", "pause"])

	def action_stop_audio(self) -> None:
		if self.audio_process and self.audio_process.poll() is None:
			self.audio_process.terminate()
			self.audio_process.wait()
			self.query_one("#audio_filename", Label).update("No audio playing")
			self.query_one("#audio_progress", AudioProgress).progress = 0.0

	def action_toggle_mute(self) -> None:
		send_mpv_cmd(["cycle", "mute"])
		self.notify("Mute toggled")

	def action_seek_m60(self) -> None:
		send_mpv_cmd(["seek", -60, "relative"])

	def action_seek_60(self) -> None:
		send_mpv_cmd(["seek", 60, "relative"])

	def action_seek_m300(self) -> None:
		send_mpv_cmd(["seek", -300, "relative"])

	def action_seek_300(self) -> None:
		send_mpv_cmd(["seek", 300, "relative"])

	def seek_absolute(self, percent: float) -> None:
		send_mpv_cmd(["seek", percent, "absolute-percent"])

	def action_vol_down(self) -> None:
		self.volume = max(0, self.volume - 5)
		send_mpv_cmd(["set_property", "volume", self.volume])

	def action_vol_up(self) -> None:
		self.volume = min(100, self.volume + 5)
		send_mpv_cmd(["set_property", "volume", self.volume])

	def action_quit(self) -> None:
		"""Save config and kill audio before the app tears down."""
		self.save_config()
		if self.audio_process and self.audio_process.poll() is None:
			self.audio_process.terminate()
		self.exit()

if __name__ == "__main__":
	app = LightFS()
	app.run()