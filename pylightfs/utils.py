import random
from pathlib import Path



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


def generate_tab_name(existing_names):
	"""Generates a unique CVC string for tab titles."""
	consonants = "bcdfghjklmnpqrstvwxyz"
	vowels = "aeiou"
	while True:
		name = random.choice(consonants) + random.choice(vowels) + random.choice(consonants)
		if name not in existing_names:
			return name

