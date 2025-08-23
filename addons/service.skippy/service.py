import os
import time
import platform
import unicodedata
import xml.etree.ElementTree as ET
import json
import re
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon

from settings_utils import is_skip_dialog_enabled
from skipdialog import SkipDialog
from segment_item import SegmentItem
from settings_utils import (
    get_user_skip_mode,
    get_edl_type_map,
    get_addon,
    log,
    log_always,
    normalize_label,
    show_overlapping_toast,
)

CHECK_INTERVAL = 1
ICON_PATH = os.path.join(get_addon().getAddonInfo("path"), "icon.png")

class PlayerMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.segment_file_found = False
        self.prompted = set()
        self.recently_dismissed = set()
        self.current_segments = []
        self.last_video = None
        self.last_time = 0
        self.shown_missing_file_toast = False
        self.playback_ready = False
        self.playback_ready_time = 0
        self.play_start_time = 0
        self.last_toast_time = 0
        self.item_metadata_ready = False
        self.last_playback_item = None
        self.last_toast_for_file = {}
        self.toast_overlap_shown = False

monitor = PlayerMonitor()
player = xbmc.Player()

def hms_to_seconds(hms):
    h, m, s = hms.strip().split(":")
    return int(h)*3600 + int(m)*60 + float(s)

def safe_file_read(*paths):
    for path in paths:
        if path:
            log(f"📂 Attempting to read: {path}")
            try:
                f = xbmcvfs.File(path)
                content = f.read()
                f.close()
                if isinstance(content, bytes):
                    content = content.decode('utf-8', errors='replace')
                if content:
                    log(f"✅ Successfully read file: {path}")
                    return content
                else:
                    log(f"⚠ File was empty: {path}")
            except Exception as e:
                log(f"❌ Failed to read {path}: {e}")
    return None

def get_video_file():
    try:
        if not player.isPlayingVideo():
            return None
        path = player.getPlayingFile()
    except RuntimeError:
        return None

    log(f"🎯 Kodi playback path: {path}")
    log(f"🔧 show_not_found_toast_for_movies: {get_addon().getSettingBool('show_not_found_toast_for_movies')}")
    log(f"🔧 show_not_found_toast_for_tv_episodes: {get_addon().getSettingBool('show_not_found_toast_for_tv_episodes')}")

    if xbmcvfs.exists(path):
        return path

    log(f"❓ Unrecognized or inaccessible path: {path}")
    return None

def infer_playback_type(item):
    showtitle = item.get("showtitle", "")
    episode = item.get("episode", -1)
    file_path = item.get("file", "")

    log(f"📺 showtitle: {showtitle}, episode: {episode}")
    normalized_path = file_path.lower()

    if showtitle:
        return "episode"
    if isinstance(episode, int) and episode > 0:
        return "episode"
    if re.search(r"s\d{2}e\d{2}", normalized_path):
        log("🧠 Fallback heuristic matched SxxExx pattern — inferring episode")
        return "episode"

    return "movie"

def should_show_missing_file_toast():
    log("🚦 Entered should_show_missing_file_toast()")

    addon = get_addon()
    show_not_found_toast_for_movies = addon.getSettingBool("show_not_found_toast_for_movies")
    show_not_found_toast_for_tv_episodes = addon.getSettingBool("show_not_found_toast_for_tv_episodes")

    query_active = {
        "jsonrpc": "2.0",
        "id": "getPlayers",
        "method": "Player.GetActivePlayers"
    }
    log(f"📨 JSON-RPC request: {json.dumps(query_active)}")
    response_active = xbmc.executeJSONRPC(json.dumps(query_active))
    log(f"📬 JSON-RPC response: {response_active}")
    active_result = json.loads(response_active)
    active_players = active_result.get("result", [])

    if not active_players:
        log("⏳ No active players — retrying after 250ms")
        xbmc.sleep(250)
        retry_response = xbmc.executeJSONRPC(json.dumps(query_active))
        log(f"📬 JSON-RPC retry response: {retry_response}")
        retry_result = json.loads(retry_response)
        active_players = retry_result.get("result", [])

    if not active_players:
        log("🚫 No active video player found — suppressing toast")
        return False, {}

    video_player = next((p for p in active_players if p.get("type") == "video"), None)
    player_id = video_player.get("playerid") if video_player else None

    if player_id is None:
        log("🚫 No video player ID found — suppressing toast")
        return False, {}

    query_item = {
        "jsonrpc": "2.0",
        "id": "VideoGetItem",
        "method": "Player.GetItem",
        "params": {
            "playerid": player_id,
            "properties": ["file", "title", "showtitle", "episode"]
        }
    }
    log(f"📨 JSON-RPC request: {json.dumps(query_item)}")
    response_item = xbmc.executeJSONRPC(json.dumps(query_item))
    item_result = json.loads(response_item)
    item = item_result.get("result", {}).get("item", {})

    if not item or "title" not in item:
        log("⚠ Player.GetItem returned empty or missing title — metadata not ready")
        return False, {}

    playback_type = infer_playback_type(item)
    log(f"🧠 Inferred playback type: {playback_type}")
    log(f"📁 File: {item.get('file')}, Title: {item.get('title')}, Showtitle: {item.get('showtitle')}, Episode: {item.get('episode')}")

    if playback_type == "movie":
        if not show_not_found_toast_for_movies:
            log("🛑 Suppressing toast — movie playback and disabled in settings")
            return False, item
        log("✅ Toast allowed — movie playback and enabled in settings")
    elif playback_type == "episode":
        if not show_not_found_toast_for_tv_episodes:
            log("🛑 Suppressing toast — episode playback and disabled in settings")
            return False, item
        log("✅ Toast allowed — episode playback and enabled in settings")
    else:
        log(f"⚠ Unknown playback type '{playback_type}' — suppressing toast")
        return False, item

    return True, item

def parse_chapters(video_path):
    base = os.path.splitext(video_path)[0]
    suffixes = ["-chapters.xml", "_chapters.xml"]
    fallback_base = None

    try:
        if player.isPlayingVideo():
            fallback_base = player.getPlayingFile().rsplit('.', 1)[0]
            log(f"🔄 Fallback base path from player: {fallback_base}")
    except RuntimeError:
        log("⚠️ getPlayingFile() failed inside parse_chapters fallback")

    paths_to_try = [f"{base}{s}" for s in suffixes]
    if fallback_base:
        paths_to_try += [f"{fallback_base}{s}" for s in suffixes]

    log(f"🔍 Attempting chapter XML paths: {paths_to_try}")
    xml_data = safe_file_read(*paths_to_try)
    if not xml_data:
        monitor.segment_file_found = False
        log("🚫 No chapter XML file found — segment_file_found set to False")
        return None

    monitor.segment_file_found = True
    log("✅ Chapter XML file found — segment_file_found set to True")

    try:
        root = ET.fromstring(xml_data)
        result = []
        for atom in root.findall(".//ChapterAtom"):
            raw_label = atom.findtext(".//ChapterDisplay/ChapterString", default="")
            label = normalize_label(raw_label)
            start = atom.findtext("ChapterTimeStart")
            end = atom.findtext("ChapterTimeEnd")
            if start and end:
                result.append(SegmentItem(
                    hms_to_seconds(start),
                    hms_to_seconds(end),
                    label,
                    source="xml"
                ))
                log(f"📘 Parsed XML segment: {start} → {end} | label='{label}'")
        if result:
            log(f"✅ Total segments parsed from XML: {len(result)}")
        else:
            log("⚠ Chapter XML parsed but no valid segments found")
        return result if result else None
    except Exception as e:
        log(f"❌ XML parse failed: {e}")
    return None

def parse_edl(video_path):
    base = video_path.rsplit('.', 1)[0]
    fallback_base = None

    try:
        if player.isPlayingVideo():
            fallback_base = player.getPlayingFile().rsplit('.', 1)[0]
            log(f"🔄 Fallback base path from player: {fallback_base}")
    except RuntimeError:
        log("⚠️ getPlayingFile() failed inside parse_edl fallback")

    paths_to_try = [f"{base}.edl"]
    if fallback_base:
        paths_to_try.append(f"{fallback_base}.edl")

    log(f"🔍 Attempting EDL paths: {paths_to_try}")
    edl_data = safe_file_read(*paths_to_try)
    if not edl_data:
        monitor.segment_file_found = False
        log("🚫 No EDL file found — segment_file_found set to False")
        return []

    monitor.segment_file_found = True
    log("✅ EDL file found — segment_file_found set to True")
    log(f"🧾 Raw EDL content:\n{edl_data}")

    segments = []
    mapping = get_edl_type_map()
    ignore_internal = get_addon().getSettingBool("ignore_internal_edl_actions")
    log(f"🔧 ignore_internal_edl_actions setting: {ignore_internal}")

    try:
        for line in edl_data.splitlines():
            parts = line.strip().split()
            if len(parts) == 3:
                s, e, action = float(parts[0]), float(parts[1]), int(parts[2])
                label = mapping.get(action)

                if ignore_internal and label is None:
                    log(f"⚠ Unrecognized EDL action type: {action} — not in mapping")
                    log(f"🚫 Ignoring unmapped EDL action {action} due to setting")
                    continue

                label = label or "segment"
                segments.append(SegmentItem(s, e, label, source="edl"))
                log(f"📗 Parsed EDL line: {s} → {e} | action={action} | label='{label}'")
    except Exception as e:
        log(f"❌ EDL parse failed: {e}")

    log(f"✅ Total segments parsed from EDL: {len(segments)}")
    return segments

def parse_and_process_segments(path):
    """
    Parses segments, filters them based on settings, and then links overlapping segments.
    """
    log(f"🚦 Starting new segment parse and process for: {path}")
    parsed = parse_chapters(path)
    if not parsed:
        parsed = parse_edl(path)
    
    if not parsed:
        log("🚫 No segment file found or parsed segments were empty.")
        return []

    # --- Pass 1: Filter segments based on user settings ---
    log("⚙️ Pass 1: Filtering segments...")
    addon = get_addon()
    skip_overlaps = addon.getSettingBool("skip_overlapping_segments")
    
    # Sort parsed segments to process them in order
    segments = sorted(parsed, key=lambda s: s.start_seconds)
    
    filtered_segments = []
    
    for current_seg in segments:
        is_overlapping_with_filtered = False
        # Check if the current segment overlaps with any already-filtered segment
        # The logic is not (end <= start or start >= end)
        for existing_seg in filtered_segments:
            if not (current_seg.end_seconds <= existing_seg.start_seconds or current_seg.start_seconds >= existing_seg.end_seconds):
                is_overlapping_with_filtered = True
                break
        
        if is_overlapping_with_filtered and skip_overlaps:
            log(f"🚫 Skipping segment {current_seg.start_seconds}-{current_seg.end_seconds} due to user setting 'skip_overlapping_segments' which detected an overlap.")
            continue
        
        filtered_segments.append(current_seg)
    
    log(f"✅ Pass 1 complete. Filtered segments: {len(filtered_segments)}")

    # --- Pass 2: Link segments for progressive skipping and detect overlaps ---
    log("🔗 Pass 2: Linking segments for progressive skipping...")
    has_overlap_or_nested = False
    
    for i in range(len(filtered_segments)):
        current_seg = filtered_segments[i]
        
        if i + 1 < len(filtered_segments):
            next_seg = filtered_segments[i+1]
            # Check for overlap with the 1-second buffer
            if next_seg.start_seconds < current_seg.end_seconds - 1:
                has_overlap_or_nested = True
                
                # Assign the jump point
                current_seg.next_segment_start = next_seg.start_seconds
                log(f"🔗 Detected overlap/nested. Setting jump point for '{current_seg.segment_type_label}' to {next_seg.start_seconds}s.")
    
    # Show toast notification if overlaps were found and setting is enabled
    if has_overlap_or_nested and show_overlapping_toast() and not monitor.toast_overlap_shown:
        xbmcgui.Dialog().notification(
            heading="Skippy",
            message="Overlapping/Nested segments detected.",
            icon=ICON_PATH,
            time=4000
        )
        monitor.toast_overlap_shown = True
        log("Toast notification displayed for overlapping segments.")
        
    log(f"✅ Pass 2 complete. Final segments to process: {len(filtered_segments)}")
    return filtered_segments

log_always("📡 XML-EDL Intro Skipper service started.")

while not monitor.abortRequested():
    if player.isPlayingVideo() or xbmc.getCondVisibility("Player.HasVideo"):
        video = get_video_file()
        if not video:
            log("⚠ get_video_file() returned None — skipping this cycle")
            monitor.last_video = None

        if video:
            # 🔁 Detect replay of same video
            if (
                video == monitor.last_video
                and monitor.playback_ready
                and player.getTime() < 5.0
                and time.time() - monitor.playback_ready_time > 5.0
            ):
                log("🔁 Replay of same video detected — resetting monitor state")
                monitor.shown_missing_file_toast = False
                monitor.prompted.clear()
                monitor.recently_dismissed.clear()
                monitor.playback_ready = False
                monitor.play_start_time = time.time()
                monitor.last_time = 0
                monitor.last_toast_time = 0
                monitor.toast_overlap_shown = False

            log(f"🚀 Entered video block — video={video}, last_video={monitor.last_video}")
            log(f"🎬 Now playing: {os.path.basename(video)}")

            if video != monitor.last_video:
                log("🆕 New video detected — resetting monitor state")
                monitor.last_video = video
                monitor.segment_file_found = False
                monitor.shown_missing_file_toast = False
                monitor.prompted.clear()
                monitor.recently_dismissed.clear()
                monitor.playback_ready = False
                monitor.play_start_time = time.time()
                monitor.last_time = 0
                monitor.last_toast_time = 0
                monitor.toast_overlap_shown = False
            
            addon = get_addon()
            try:
                allow_toast, item = should_show_missing_file_toast()
                playback_type = infer_playback_type(item)
                log(f"🔍 Playback type inferred via toast logic: '{playback_type}'")
            except Exception as e:
                log(f"❌ Failed to infer playback type via toast logic: {e}")
                playback_type = ""
                item = None

            show_dialogs = is_skip_dialog_enabled(playback_type)
            toast_movies = addon.getSettingBool("show_not_found_toast_for_movies")
            toast_episodes = addon.getSettingBool("show_not_found_toast_for_tv_episodes")

            log(f"🧪 Raw setting values → show_dialogs: {show_dialogs}, show_not_found_toast_for_movies: {toast_movies}, show_not_found_toast_for_tv_episodes: {toast_episodes}")

            if not playback_type:
                log("⚠ Playback type not detected — skipping segment parsing")
                monitor.current_segments = []
            else:
                monitor.current_segments = parse_and_process_segments(video) or []
                log(f"📦 Parsed {len(monitor.current_segments)} segments for playback_type: {playback_type}")

            if not show_dialogs:
                log(f"🚫 Skip dialogs disabled for {playback_type} — segments will not trigger prompts")

        try:
            current_time = player.getTime()
            log(f"🧪 Current playback time: {current_time}")
        except RuntimeError:
            log("⚠ player.getTime() failed — no media playing")
            continue

        rewind_threshold = get_addon().getSettingInt("rewind_threshold_seconds")
        if current_time < monitor.last_time and monitor.last_time - current_time > rewind_threshold:
            log(f"⏪ Significant rewind detected ({monitor.last_time:.2f} → {current_time:.2f}) — threshold: {rewind_threshold}s")
            monitor.prompted.clear()
            monitor.recently_dismissed.clear()
            log("🧹 recently_dismissed cleared due to rewind")

        if not monitor.playback_ready and current_time > 0:
            monitor.playback_ready = True
            monitor.playback_ready_time = time.time()
            log("✅ Playback confirmed via getTime() — setting playback_ready = True")

        if (
            monitor.playback_ready
            and not monitor.shown_missing_file_toast
            and time.time() - monitor.playback_ready_time >= 2
            and not monitor.segment_file_found
        ):
            log("⚠ [TOAST BLOCK] Entered toast logic block")
            try:
                toast_enabled = (
                    (playback_type == "movie" and toast_movies) or
                    (playback_type == "episode" and toast_episodes)
                )

                if toast_enabled:
                    cooldown = 6
                    now = time.time()
                    if now - monitor.last_toast_time >= cooldown:
                        msg_type = "episode" if playback_type == "episode" else "movie"

                        xbmcgui.Dialog().notification(
                            heading="Skippy",
                            message=f"No skip segments found for this {msg_type}.",
                            icon=ICON_PATH,
                            time=3000,
                            sound=False
                        )
                        monitor.last_toast_time = now
                        log(f"⚠ [TOAST BLOCK] Toast displayed for {msg_type}")
                    else:
                        log(f"⏳ [TOAST BLOCK] Suppressed — cooldown active ({int(now - monitor.last_toast_time)}s since last toast)")
                else:
                    log("✅ [TOAST BLOCK] Toast suppressed — toast toggle disabled for this type")
            except Exception as e:
                log(f"❌ [TOAST BLOCK] should_show_missing_file_toast() failed: {e}")
            monitor.shown_missing_file_toast = True

        if not monitor.playback_ready:
            log("⏳ Playback not ready — waiting before processing segments")
            monitor.last_time = current_time
            continue

        for segment in monitor.current_segments:
            seg_id = (int(segment.start_seconds), int(segment.end_seconds))
            
            if seg_id in monitor.prompted:
                log(f"⏭ Segment {seg_id} already prompted — skipping")
                continue
                
            if seg_id in monitor.recently_dismissed:
                log(f"🙅 Segment {seg_id} is in recently_dismissed — skipping")
                continue

            if not segment.is_active(current_time):
                log(f"⏳ Segment {seg_id} not active at {current_time:.2f} — skipping")
                continue
            
            log(f"🔎 Raw segment label before skip mode check: '{segment.segment_type_label}'")
            behavior = get_user_skip_mode(segment.segment_type_label)
            log(f"🧪 Segment behavior for '{segment.segment_type_label}': {behavior}")

            if not show_dialogs and behavior == "ask":
                log(f"🚫 Dialogs disabled in settings — suppressing 'ask' behavior for segment {seg_id}")
                monitor.prompted.add(seg_id)
                continue  
            if behavior == "never":
                log(f"🚫 Skipping dialog for '{segment.segment_type_label}' (user preference: never)")
                continue

            log(f"🕒 Active segment: {segment.segment_type_label} [{segment.start_seconds}-{segment.end_seconds}] → {behavior}")
            log(f"📘 Segment source: {segment.source}")

            # Correctly handle jump point from the new logic
            jump_to = segment.next_segment_start if segment.next_segment_start is not None else segment.end_seconds + 1.0

            if behavior == "auto":
                log(f"⚙ Auto-skip behavior triggered for segment ID {seg_id} ({segment.segment_type_label})")
                player.seekTime(jump_to)
                monitor.last_time = jump_to
                monitor.prompted.add(seg_id)

                if addon.getSettingBool("show_toast_for_skipped_segment"):
                    log("🔔 Showing toast notification for auto-skipped segment")
                    xbmcgui.Dialog().notification(
                        heading="Skipped",
                        message=f"{segment.segment_type_label.title()} skipped",
                        icon=ICON_PATH,
                        time=2000,
                        sound=False
                    )
                else:
                    log("🔕 Skipped segment toast disabled by user setting")

                log(f"⚡ Auto-skipped to {jump_to}")

            elif behavior == "ask":
                log(f"🧠 Ask-skip behavior triggered for segment ID {seg_id} ({segment.segment_type_label})")

                if not player.isPlayingVideo():
                    log("⚠ Playback not active — skipping dialog")
                    monitor.prompted.add(seg_id)
                    continue

                try:
                    log("🛑 Debouncing skip dialog for 300ms")
                    xbmc.sleep(300)

                    layout_value = addon.getSetting("skip_dialog_position").replace(" ", "")
                    dialog_name = f"SkipDialog_{layout_value}.xml"
                    log(f"📐 Using skip dialog layout: {dialog_name}")

                    dialog = SkipDialog(dialog_name, addon.getAddonInfo("path"), "default", segment=segment)
                    dialog.doModal()
                    confirmed = getattr(dialog, "response", None)
                    del dialog

                    if confirmed:
                        log(f"✅ User confirmed skip for segment ID {seg_id}")
                        monitor.prompted.add(seg_id)
                        player.seekTime(jump_to)
                        monitor.last_time = jump_to

                        if addon.getSettingBool("show_toast_for_skipped_segment"):
                            log("🔔 Showing toast notification for user-confirmed skip")
                            xbmcgui.Dialog().notification(
                                heading="Skipped",
                                message=f"{segment.segment_type_label.title()} skipped",
                                icon=ICON_PATH,
                                time=2000,
                                sound=False
                            )
                        else:
                            log("🔕 Skipped segment toast disabled by user setting")

                        log(f"🚀 Jumped to {jump_to}")
                    else:
                        log(f"🙅 User dismissed skip dialog for segment ID {seg_id}")
                        monitor.recently_dismissed.add(seg_id)
                        monitor.prompted.add(seg_id)
                except Exception as e:
                    log(f"❌ Error showing skip dialog: {e}")
                    monitor.prompted.add(seg_id)
                    continue

            monitor.last_time = current_time


    if monitor.waitForAbort(CHECK_INTERVAL):
        log("🛑 Abort requested — exiting monitor loop")