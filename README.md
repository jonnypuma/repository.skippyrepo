# repository.skippyrepo
Repository for the Kodi addon: Skippy - Video Segment Skipper 
<img width="1024" height="1024" alt="icon" src="https://github.com/user-attachments/assets/a9566ad0-f74c-45b7-8243-85357f33b194" />
# 📼 Skippy — The XML-EDL Segment Skipper

Skippy is a Kodi service that detects and can skip predefined video segments such as intros, recaps, ads, or credits using companion `.xml` or `.edl` files. 

Supports chaptered Matroska XML files and Mplayer/Kodi style EDL files.
 
It provides both automatic and user-prompted skipping, and integrates seamlessly into playback with customizable notifications and dialogs.

Discreet, cross-platform, and customizable.

---

✅ Supported Kodi Versions and Platforms

Tested on **Kodi Omega 21.2** across:

| Platform       			        | Status     |
|---------------------------|------------|
| Android (Nvidia Shield) 	 | ✅ Tested |
| Linux (CoreELEC)  		      | ✅ Tested |
| Windows 11       			      | ✅ Tested |

---

## 🚀 Key Features

- ⏭️ User-configurable skip behavior: Auto-skip, prompt, or ignore segments based on per-label rules.
- 📁 File format support: Supports Matroska-style `.xml` chapters and enhanced `.edl` format
- 🧠 Smart playback type detection: Infers playback type and detects whether you're watching a movie or TV episode using metadata and filename heuristics.
- 🔍 Playback-aware toast notifications: Notifies when no skip metadata is found — only if enabled in settings.
- 🧠 Label logic allows fine-grained control: `"intro"`, `"recap"`, `"ads"`, etc.
- 🛡️ Platform-agnostic compatibility: Works seamlessly across Android, Windows, CoreELEC, and Linux.
- 📊 Progress Bar Display toggle: Progress bar which fills up until end of segment. On/off toggle available under settings.
- 🖼️ Skip Dialog Placement: Choose dialog layout position (Center, Top, Bottom, Side)
- ⏪ Rewind detection logic: Resets skip prompts only on significant rewinds — with a user-defined threshold.
- 📺 Toast segment file not-found notification filtering: Notifies when no segments were found for the current video. Toggle on/off for movies or TV episodes, or always on (Always Show Toast override). Supports per-playback cooldown (default: 6 seconds)
- 🧹 Debug logging: Verbose logs for each segment processed and decision made. Toggle on/off.

---

🎬 Play the Video

Start playback of MyMovie.mkv in Kodi. Skippy will:

1. Search for XML or EDL metadata file alongside the video.

2. Try to read .xml first, then .edl as fallback. Parses segment list and stores in memory

3. Match segment labels

4. Skip, prompt or never ask based on your preferences

5. Show a toast if no segments are found (if enabled)

Each second:
- Checks current time against segment list
- If within an active segment: Applies skip behavior
- Flags as prompted to avoid repeats
- Checks current playback time
- If a matching segment becomes active, Skippy will based on label behavior defined in settings:
```xml
    ⏩ Skip automatically 
    ❓ Prompt the user
    🚫 Do nothing 
```
- Remembers if a segment is dismissed to avoid repeat prompts (unless user seeks back), i.e. at stop, end, or rewind: clears segment cache and skip history

<img width="2559" height="1599" alt="screenshot01" src="https://github.com/user-attachments/assets/c684b0b4-0d01-4908-8c00-f229984274b1" />
<img width="2559" height="1599" alt="screenshot02" src="https://github.com/user-attachments/assets/e4dfe5d3-fb4d-45e2-892a-ed721b8b8781" />
<img width="2559" height="1599" alt="screenshot03" src="https://github.com/user-attachments/assets/59602deb-c5c5-4f9f-98e6-fdc2578b5cc5" />

---

🧪Forced cache clearing

Force cache clearing (reparse segments every time), to avoid Kodi cache remembering what you have skipped if you want to restart a playback for instance.

Done by:
python
monitor.last_video = None

Force prompt for testing:
python
if True:  # triggers skip dialog

---

⚙️ Settings

Found under:  
`Settings → Add-ons → My Add-ons → Services → Skippy - Video Segment Skipper`

<img width="2559" height="1599" alt="screenshot04" src="https://github.com/user-attachments/assets/b2ee73d6-2cdb-49a4-ac8d-e0f8b385cc05" />

⚙ Default settings Overview
Default settings file loaded at first start located in: .../addons/service.skippy/resources/settings.xml
Setting	Description:

Category: Segment Settings
- custom_segment_keywords       Comma-separated list of labels (case-insensitive) the skipper should monitor
- segment_always_skip			Comma-separated list of segment labels to skip automatically
- segment_ask_skip			    Comma-separated list of labels to prompt for skipping
- segment_never_skip			Comma-separated list of labels to never skip
- ignore_kodi_edl_actions       Default value - true
- edl_action_mapping			Map .edl action codes to skip labels (e.g. 4:intro,5:credits)

Category: Customize Skip Dialog Look and Behavior
- show_progress_bar			    Enables visual progress bar during skip dialog
- skip_dialog_position	    	Chooses layout position for the skip confirmation dialog
- rewind_threshold_seconds	    Threshold for detecting rewind and clearing dialog suppression states
- show_skip_dialog_movies	    Show skip dialog for movies when behavior is set to ask	
- show_skip_dialog_episodes	    Show skip dialog for TV episodes when behavior is set to ask

Category: Not Found Toast notifications
- always_show_missing_toast	    Forces toast to show even when movie/episode toggles are disabled
- enable_for_movies			    Skip support toggle for movie playback
- enable_for_tv_episodes		Skip support toggle for episode playback


Category: Debug Logging
- enable_verbose_logging		Enables extra log entries for debugging

---

🧠 Skip Modes examples

Segment behavior is matched via normalized labels and defined in:

- segment_always_skip
- segment_ask_skip
- segment_never_skip

Examples:
```xml
segment_always_skip = commercial, ad
segment_ask_skip = intro, recap, credits, pre-roll
segment_never_skip = logo, preview, prologue, epilogue, main
```

---

📁 File Support
Skippy supports the following segment definition files:

- filename.edl
- filename-chapters.xml
. filename_chapters.xml

These should reside in the same directory as the video file. EDL files follow Kodi’s native format with start, end, and action code lines. XML files use a chapter-based structure. See section below.

---

🧩 File Example
Breaking.Bad.S01E02.mkv
```xml
├── Breaking.Bad.S01E02-chapters.xml or Breaking.Bad.S01E02_chapters.xml    # XML chapter file
└── Breaking.Bad.S01E02.edl                                                 # Fallback if no XML found
```
XML takes priority if both exist.

---

📁 Metadata Formats
Skippy supports two segment metadata formats, placed alongside the .mkv or video file:

1. ✅ XML Chapter Files (Preferred)

- Filenames: filename-chapters.xml or filename_chapters.xml
- Format: Matroska-style (e.g. exported by Jellyfin)
- Label: `<ChapterString>Intro</ChapterString>`
- Configurable behavior per label: auto-skip / ask to skip / never

2. ✅ Enhanced EDL Files (Fallback)

- Filename: `filename.edl`
- Format: <start_time> <end_time> <action_type>
- Configurable behavior per label: auto-skip / ask-to-skip / never (shares the same label settings as the xml route)

📄 Sample Segment Files
EDL files define skip segments using three values per line

🧾 .edl File Content Example:
```xml
210 235 4 
```
→ Will skip or prompt from 3:30 to 3:55 if action type `4` is mapped to `'Intro'` 

```xml
Format: <start_time> <end_time> <action_type>. start_time and end_time are in seconds. action type is an integer between 4 to 99
```
Action mapping: action_code maps to a label via edl_action_mapping (e.g. 4:intro, 5:credits)


ℹ️ Kodi may log a warning for unknown EDL action types — this is expected and harmless.

Custom action types (4–99) are supported amd configurable via settings:
4 → Segment (default)
5 → Intro
6 → Ad, etc. — 

If no label is present in edl file or defined in settings, 'Segment' is used as fallback

📘 .xml Chapter Format

XML files define segments using chapter metadata:

```xml
<Chapters>
  <EditionEntry>
    <ChapterAtom>
      <ChapterTimeStart>00:00:00.000</ChapterTimeStart>
      <ChapterTimeEnd>00:01:00.000</ChapterTimeEnd>
      <ChapterDisplay>
        <ChapterString>Intro</ChapterString>
      </ChapterDisplay>
    </ChapterAtom>
    <ChapterAtom>
      <ChapterTimeStart>00:20:00.000</ChapterTimeStart>
      <ChapterTimeEnd>00:21:00.000</ChapterTimeEnd>
      <ChapterDisplay>
        <ChapterString>Credits</ChapterString>
      </ChapterDisplay>
    </ChapterAtom>
  </EditionEntry>
</Chapters>
```

Here’s a breakdown of the chapters:
- Intro: 00:00–01:00
- Credits: 20:00–21:00

ChapterString is the label used for skip mode matching

Times must be in HH:MM:SS.mmm format

Labels are normalized (e.g. Intro, intro, INTRO all match)

---

✅ Segment Behavior Logic Summary
|Behavior	  |   Dialogs Enabled (show_dialogs = True)	    |   Dialogs Disabled (show_dialogs = False) |
|-----------|---------------------------------------------|-------------------------------------------|
|never	     |      ❌ Skip silently	                      |      ❌ Skip silently                    |
|ask	       |      ✅ Show dialog	                        |      ❌ Suppress dialog                  |
|auto	      |      ✅ Skip automatically	                 |      ✅ Skip automatically               |

If show_skip_dialog_movies = False, then dialogs will be suppressed for movie segments even if their behavior is "ask".

If show_skip_dialog_episodes = False, then dialogs will be suppressed for episode segments with "ask" behavior.

This suppression is independent of the segment file presence or toast settings.

✅ Example
If a segment in a movie has behavior "ask" and show_skip_dialog_movies = False, the dialog will not appear. Instead, the segment will be silently skipped or ignored depending on other settings.

When is the missing segment file toast notifcation displayed:
|Skip Dialog Enabled   |   Segment File Present   |   Toast Enabled   |   Show Toast? |
|----------------------|--------------------------|-------------------|----------------|
|✅ Yes	               |     ✅ Yes	             |    ✅ Yes	        |    ❌ No      |
|✅ Yes	               |     ❌ No	               |    ✅ Yes	       |    ✅ Yes     |
|❌ No	                |     ✅ Yes	             |    ✅ Yes	        |    ❌ No      |
|❌ No	                |     ❌ No	               |    ✅ Yes	       |    ✅ Yes     |
|❌ No	                |     ❌ No	               |    ❌ No	        |    ❌ No      |
|✅ Yes	               |     ❌ No	               |    ❌ No	        |    ❌ No      |
|❌ No	                |     ✅ Yes	             |    ❌ No	         |    ❌ No      |

---

🚀 Usage Examples

✅ Auto-skip

If your chapters.xml contains:

<ChapterString>Intro</ChapterString>

And you've configured "Intro" to auto-skip, the addon will jump past it without prompting.

❓ Ask to skip

If your .edl file contains:

0.0 90.0 9
And action code 9 maps to "Recap", and "Recap" is mapped to the "Ask to skip" setting, you'll be prompted to skip it.


🔕 Never skip example

If your segment label is "Credits" and you've mapped "Credits" to the "Never skip" setting, playback continues uninterrupted with no skip popup.

---

### 🎛️ EDL Action Filtering

Skippy supports optional filtering of Kodi-native EDL action types (`0`, `1`, `2`, `3`). This allows users to ignore internal skip markers and rely only on custom-defined segments.

#### 🔧 Setting
- **Name:** `ignore_kodi_edl_actions`
- **Type:** Boolean
- **Default:** `true`

#### ✅ Behavior
| Setting Value | Action Types Parsed | Result |
|---------------|---------------------|--------|
| `true`        | Only custom actions (`>=4`) | Internal Kodi skip markers are ignored |
| `false`       | All action types     | Autoskip or prompt for all segments, including Kodi-native ones |

#### 📝 Example
```edl
237.5    326.326    5    intro
1323.45  1429.184   2    segment

---

🍿 Toast Notification Behavior

- Appears when a video has no matching skip segments
- Suppressed if filtered by playback type unless always_show_missing_toast is enabled

Cooldown enforced per playback session (default: 6 seconds)

- Resets on video stop or replay after cooldown

---

🚨 Logging

Verbose logging reveals:

- Parsed segments and labels
- Playback state and detection
- Toast decision logic and suppression
- Skip dialog flow and user choice
- Enable via enable_verbose_logging for full insight.

---

🔄 Batch EDL Action Type Normalizer (Windows)

Located in tools/edl-updater.bat:

Updates all .edl files under a folder recursively

Replaces old action types with new ones (e.g. 3 → 4)

User can specify which action type to look for and which action type to replace with in accordance with user specifications in the settings.xml file.

Ensures full compatibility with Skippy’s behavior mappings

---

🧾 License & Credits

Not affiliated with Jellyfin, Kodi, MPlayer or Matroska

white.png background courtesy of im85288 (Up Next add-on)

___________________________________________________________________________________


🧼 Developer Notes
- UI driven by WindowXMLDialog
- EDL action types 0 and 3 (Kodi-native) are ignored by the addon due to them being used by Kodi's internal autoskip feature
- Only -chapters.xml and _chapters.xml and .edl files are scanned

---

🧑‍💻 Contributors

jonnyp — Architect, debugger
