Kodi repository for:

<img width="1200" height="1200" alt="icon" src="https://github.com/user-attachments/assets/56b02adc-6002-4a72-8936-446b077575b3" />

# Skippy — The XML-EDL Segment Skipper

Skippy is a Kodi service that detects and can skip predefined video segments such as intros, recaps, ads, or credits using companion `.xml` or `.edl` files. 

- Reads companion metadata files (Matroska-style .xml chapter files or MPlayer-style .edl files) placed alongside video files to identify skip-worthy segments.
- Provides both automatic and user-prompted skipping, and integrates seamlessly into playback with customizable notifications and dialogs.
- It detects playback type (movie vs. TV episode) using metadata and filename heuristics, and can show customizable skip dialogs with progress bars at configurable screen positions. 
- Handles complex scenarios like nested and overlapping segments, intelligently managing parent-child relationships so dialogs appear at the right times. 
- Includes rewind detection that resets skip prompts only on significant rewinds, and respects user dismissals so dismissed segments don't reappear after pause/resume.
- Provides optional toast notifications when no segment files are found, supports multiple button focus styles, and includes debug logging.

Supported Video Formats: Works for MKV and AVI containers.

Discreet, cross-platform, and customizable.

Tested on Kodi Omega 21.2 across Android, Linux (CoreELEC), and Windows platforms, Skippy works with MKV and AVI containers but has known limitations with MP4 files due to Kodi constraints.

Known Limitations: Video files in MP4 containers are currently not working, seems to be a Kodi issue and not addon issue.

---

<img width="815" height="810" alt="icon" src="https://github.com/user-attachments/assets/542b71c5-dcdc-44cc-ac35-46a86ada9dc7" />

# Segment Editor

Segment Editor is a Kodi service addon for editing EDL and chapter.xml segment files during video playback and a companion service to the Skippy Segment Skipper addon. 

It supports both EDL (Edit Decision List) and Matroska chapter XML formats, with automatic detection that prefers chapters.xml over .edl files. The editor can be opened via keyboard shortcut (default CTRL+E), remote control key mapping, or trigger file, and works while the video plays in the background.

The interface includes a segment list showing all segments with labels, times, and durations, plus real-time playback controls. 

You can pause/resume playback, seek precisely with buttons (-30s to +30s), and mark start/end points for segment creation. Segments can be added using marked times, at the current playback position with a user-set duration, or by manually entering start and end times. Pressing Enter/Select on a list item jumps playback to the start of that segment for quick navigation.

The addon provides visual indicators for nested segments (fully contained within another) and overlapping segments (partially overlapping), helping identify potential conflicts. 

Edit and Delete buttons appear next to each segment, and you can modify start times, end times, and labels. Keyboard shortcuts (Space for pause, S for start, E for end, D for delete) provide quick access to common functions. 

Segments are automatically sorted by start time, and the addon supports both predefined labels (configurable in settings) and custom labels. Changes can be saved to EDL, XML, or both formats based on your preferences, making it easy to create and manage skip segments for intros, recaps, credits, or any other video sections.

---

Contributors
jonnyp — Architect, debugger

---
