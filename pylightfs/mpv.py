import json
import socket
import uuid



SOCKET_PATH = f"/tmp/lightfs_mpv_{uuid.uuid4()}.sock"


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
