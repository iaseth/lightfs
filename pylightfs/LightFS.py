import subprocess
import json
import time
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import TabbedContent, TabPane, ListView, Label

from .AudioProgress import AudioProgress
from .FMListView import FMListView
from .FMTab import FMTab
from .HelpScreen import HelpScreen
from .PathItem import PathItem

from .constants import AUDIO_EXTENSIONS
from .mpv import send_mpv_cmd, SOCKET_PATH
from .utils import format_time, generate_tab_name



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
	#p1 { width: 20%; }
	#p2 { width: 20%; }
	#p3 { width: 60%; }
	
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
		Binding("o", "prev_tab", "Prev Tab"),
		Binding("p", "next_tab", "Next Tab"),
		Binding("1", "goto_tab(1)", show=False),
		Binding("2", "goto_tab(2)", show=False),
		Binding("3", "goto_tab(3)", show=False),
		Binding("4", "goto_tab(4)", show=False),
		Binding("5", "goto_tab(5)", show=False),
		Binding("6", "goto_tab(6)", show=False),
		Binding("7", "goto_tab(7)", show=False),
		Binding("8", "goto_tab(8)", show=False),
		Binding("9", "goto_tab(9)", show=False),
		Binding("0", "goto_tab(0)", show=False),
		Binding("left", "focus_left", "Focus Left"),
		Binding("right", "focus_right", "Focus Right"),
		Binding("u", "go_up", "Go Up"),
		Binding("b", "toggle_bookmark", "Bookmark"),
		Binding(".", "toggle_hidden", "Toggle Hidden"),
		Binding("S", "set_global_start", "Set Start"),
		Binding("s", "go_start", "Go Start"),
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
		self.current_track_name = ""
		self.current_track_path = None
		self.current_audio_time = 0.0
		self.audio_history = {}
		self.volume = 100
		self.max_tabs = 99
		self.show_hidden = False
		
		self.start_dir = Path.home()
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
		active_tab_index = 0
		if self.config_file.exists():
			try:
				with open(self.config_file, "r") as f:
					data = json.load(f)
					
				self.start_dir = Path(data.get("start_dir", Path.home()))
				if not self.start_dir.exists(): self.start_dir = Path.home()
				
				hist = data.get("audio_history", {})
				now = time.time()
				for k, v in hist.items():
					if now - v.get("timestamp", 0) <= 28 * 24 * 3600:
						self.audio_history[k] = v

				saved_bms = data.get("bookmarks", [])
				if saved_bms:
					self.bookmarks = [Path(p) for p in saved_bms if Path(p).exists()]
					
				tabs_data = data.get("tabs", [])
				active_tab_index = data.get("active_tab_index", 0)
			except Exception:
				pass
		
		tc = self.query_one(TabbedContent)
		if tabs_data:
			existing_names = set()
			for t in tabs_data:
				c_dir = Path(t.get("current_dir", self.start_dir))
				if not c_dir.exists(): c_dir = self.start_dir
				
				t_name = generate_tab_name(existing_names)
				existing_names.add(t_name)
				tab_id = f"tab-{t_name}"
				
				new_tab = FMTab(t_name, c_dir, id=tab_id)
				tc.add_pane(new_tab)
				
			tabs = list(tc.query(TabPane))
			if tabs and 0 <= active_tab_index < len(tabs):
				tc.active = tabs[active_tab_index].id
		else:
			self.action_new_tab()

	def save_config(self) -> None:
		self.config_file.parent.mkdir(parents=True, exist_ok=True)
		tabs_data = []
		active_tab_idx = 0
		
		try:
			tc = self.query_one(TabbedContent)
			active_id = tc.active
			tabs = list(tc.query(TabPane))
			for i, t in enumerate(tabs):
				if t.id == active_id:
					active_tab_idx = i
					break
		except Exception:
			pass
		
		for tab in self.query(FMTab):
			tabs_data.append({"current_dir": str(tab.current_dir)})
			
		data = {
			"start_dir": str(self.start_dir),
			"active_tab_index": active_tab_idx,
			"bookmarks": [str(b) for b in self.bookmarks],
			"tabs": tabs_data,
			"audio_history": self.audio_history
		}
		try:
			with open(self.config_file, "w") as f:
				json.dump(data, f, indent=4)
		except Exception:
			pass

	def save_current_audio_state(self) -> None:
		if self.audio_process and self.audio_process.poll() is None and self.current_track_path:
			pos_resp = send_mpv_cmd(["get_property", "time-pos"])
			if pos_resp and 'data' in pos_resp:
				self.current_audio_time = pos_resp['data']
				
		if self.current_track_path and self.current_audio_time is not None:
			track_key = str(self.current_track_path)
			if self.current_audio_time >= 300: 
				self.audio_history[track_key] = {
					"time": self.current_audio_time,
					"timestamp": time.time()
				}
			else:
				self.audio_history.pop(track_key, None)

	def update_player_ui(self) -> None:
		if not self.audio_process or self.audio_process.poll() is not None:
			return

		pos_resp = send_mpv_cmd(["get_property", "time-pos"])
		dur_resp = send_mpv_cmd(["get_property", "duration"])

		if pos_resp and dur_resp and 'data' in pos_resp and 'data' in dur_resp:
			pos = pos_resp['data']
			dur = dur_resp['data']
			self.current_audio_time = pos
			
			if dur > 0:
				self.query_one("#audio_progress", AudioProgress).progress = pos / dur
				self.query_one("#audio_filename", Label).update(
					f"🎵 {self.current_track_name}   [{format_time(pos)} / {format_time(dur)}]   Vol: {self.volume}%"
				)

	def execute_path(self, path: Path) -> None:
		"""Centralized handler for Enter keys and Double Clicks."""
		if path.is_dir():
			tc = self.query_one(TabbedContent)
			tab = tc.active_pane
			if isinstance(tab, FMTab):
				tab.current_dir = path
				tab.refresh_p2()
				tab.query_one("#p2", FMListView).focus()
		else:
			self.open_file(path)

	def get_existing_tab_names(self):
		return {tab.tab_name for tab in self.query(FMTab)}

	def action_new_tab(self) -> None:
		tc = self.query_one(TabbedContent)
		if tc.tab_count < self.max_tabs:
			t_name = generate_tab_name(self.get_existing_tab_names())
			tab_id = f"tab-{t_name}"
			new_tab = FMTab(t_name, self.start_dir, id=tab_id)
			tc.add_pane(new_tab)
			tc.active = tab_id
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

	def action_goto_tab(self, num: int) -> None:
		tc = self.query_one(TabbedContent)
		tabs = list(tc.query(TabPane))
		if not tabs: return
		
		if num == 0:
			tc.active = tabs[-1].id
		else:
			idx = num - 1
			if idx < len(tabs):
				tc.active = tabs[idx].id

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
		try: event.pane.query_one("#p2", FMListView).focus()
		except Exception: pass

	def action_focus_left(self) -> None: self.move_pane_focus(-1)
	def action_focus_right(self) -> None: self.move_pane_focus(1)

	def move_pane_focus(self, direction: int) -> None:
		tc = self.query_one(TabbedContent)
		active_tab = tc.active_pane
		if not active_tab: return
		panes = list(active_tab.query(FMListView))
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
			tab.query_one("#p2", FMListView).focus()

	def action_toggle_hidden(self) -> None:
		self.show_hidden = not self.show_hidden
		self.notify(f"Hidden files: {'Shown' if self.show_hidden else 'Hidden'}")
		tc = self.query_one(TabbedContent)
		tab = tc.active_pane
		if isinstance(tab, FMTab):
			tab.refresh_p2()
			if len(tab.query_one("#p2", FMListView).children) == 0:
				tab.query_one("#p3", FMListView).clear()

	def action_set_global_start(self) -> None:
		tc = self.query_one(TabbedContent)
		tab = tc.active_pane
		if isinstance(tab, FMTab):
			self.start_dir = tab.current_dir
			self.notify(f"Global Start set to: {self.start_dir}")

	def action_go_start(self) -> None:
		tc = self.query_one(TabbedContent)
		tab = tc.active_pane
		if isinstance(tab, FMTab):
			tab.current_dir = self.start_dir
			tab.refresh_p2()
			tab.query_one("#p2", FMListView).focus()

	def action_toggle_bookmark(self) -> None:
		focused = self.focused
		if not isinstance(focused, FMListView): return
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
		if path.suffix.lower() in AUDIO_EXTENSIONS:
			self.save_current_audio_state()
			
			if self.audio_process and self.audio_process.poll() is None:
				self.audio_process.terminate()
				self.audio_process.wait()
				
			self.current_track_path = path
			self.current_track_name = path.name
			
			start_pos = 0
			if str(path) in self.audio_history:
				start_pos = self.audio_history[str(path)].get("time", 0)
			
			self.audio_process = subprocess.Popen(
				["mpv", "--no-video", f"--start={start_pos}", f"--input-ipc-server={SOCKET_PATH}", str(path)],
				stdin=subprocess.DEVNULL,
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL
			)
			send_mpv_cmd(["set_property", "volume", self.volume])
		else:
			subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			self.notify(f"Opened: {path.name}")

	def action_toggle_play(self) -> None:
		send_mpv_cmd(["cycle", "pause"])

	def action_stop_audio(self) -> None:
		if self.audio_process and self.audio_process.poll() is None:
			self.save_current_audio_state()
			self.audio_process.terminate()
			self.audio_process.wait()
			
			self.current_track_path = None
			self.query_one("#audio_filename", Label).update("No audio playing")
			self.query_one("#audio_progress", AudioProgress).progress = 0.0

	def action_toggle_mute(self) -> None:
		send_mpv_cmd(["cycle", "mute"])
		self.notify("Mute toggled")

	def action_seek_m60(self) -> None: send_mpv_cmd(["seek", -60, "relative"])
	def action_seek_60(self) -> None: send_mpv_cmd(["seek", 60, "relative"])
	def action_seek_m300(self) -> None: send_mpv_cmd(["seek", -300, "relative"])
	def action_seek_300(self) -> None: send_mpv_cmd(["seek", 300, "relative"])

	def seek_absolute(self, percent: float) -> None:
		send_mpv_cmd(["seek", percent, "absolute-percent"])

	def action_vol_down(self) -> None:
		self.volume = max(0, self.volume - 5)
		send_mpv_cmd(["set_property", "volume", self.volume])

	def action_vol_up(self) -> None:
		self.volume = min(100, self.volume + 5)
		send_mpv_cmd(["set_property", "volume", self.volume])

	def action_quit(self) -> None:
		self.save_current_audio_state()
		self.save_config()
		if self.audio_process and self.audio_process.poll() is None:
			self.audio_process.terminate()
		self.exit()

