# MediaPlaylist

MediaPlaylist is a single-file local media launcher focused on card-based playlists.

It runs a small local HTTP server and opens a browser UI where you can create groups, assign media files to cards, and play images, videos, audio, and PDFs from your own computer.

## Features

- Card-first media launcher UI
- Multiple card groups
- Drag files onto cards to assign media
- Optional custom thumbnails and thumbnail focus control
- In-browser playback for images, videos, audio, and PDFs
- External opening for presentations and documents
- Local-only data storage
- No cloud service required

## Run

```powershell
python MediaPlaylist.py
```

Then open:

```text
http://localhost:8765
```

## Notes

- The app stores local settings in the app data directory.
- If a browser does not expose a dragged file path, MediaPlaylist imports a copy into its local `imported/` folder.
- Optional thumbnail generation for videos may require `ffmpeg`.

## License

Add your preferred open-source license before publishing to GitHub.
