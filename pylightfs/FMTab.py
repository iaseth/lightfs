from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import TabPane, ListView, ListItem

from .FMListView import FMListView
from .PathItem import PathItem
from .utils import get_filtered_paths



class FMTab(TabPane):
	def __init__(self, title: str, current_dir: Path, *args, **kwargs):
		super().__init__(title, *args, **kwargs)
		self.tab_name = title 
		self.current_dir = current_dir

	def compose(self) -> ComposeResult:
		with Horizontal():
			yield FMListView(id="p1")
			yield FMListView(id="p2")
			yield FMListView(id="p3")

	def on_mount(self) -> None:
		self.populate_bookmarks()
		self.refresh_p2()

	def populate_bookmarks(self) -> None:
		p1 = self.query_one("#p1", FMListView)
		p1.clear()
		for bm in self.app.bookmarks:
			p1.append(PathItem(bm))

	def refresh_p2(self) -> None:
		p2 = self.query_one("#p2", FMListView)
		p2.clear()
		for p in get_filtered_paths(self.current_dir, self.app.show_hidden):
			p2.append(PathItem(p))

	def refresh_p3(self, target_dir: Path) -> None:
		p3 = self.query_one("#p3", FMListView)
		p3.clear()
		for p in get_filtered_paths(target_dir, self.app.show_hidden):
			p3.append(PathItem(p))

	def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
		"""Update p3 only when a directory is highlighted. Leaves p3 intact for files."""
		if event.list_view.id == "p2":
			item = event.item
			if isinstance(item, PathItem) and item.path.is_dir():
				self.refresh_p3(item.path)


