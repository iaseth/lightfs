from pylightfs import LightFS


if __name__ == "__main__":
	try:
		app = LightFS()
		app.run()
	except Exception as e:
		app.close_audio_process()
		print(f"Exception: {e}")
