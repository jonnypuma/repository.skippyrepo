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

from skipdialog import SkipDialog
from segment_item import SegmentItem
from settings_utils import (
    get_user_skip_mode,
    get_edl_type_map,
)

def get_addon():
    return xbmcaddon.Addon()
    
CHECK_INTERVAL = 1

ICON_PATH = os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "icon.png")


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



def log(msg):
    if get_addon().getSettingBool("enable_verbose_logging"):
        xbmc.log(f"[XML-EDL Skipper] {msg}", xbmc.LOGINFO)

def log_always(msg):
    xbmc.log(f"[XML-EDL Skipper] {msg}", xbmc.LOGINFO)

def normalize_label(text):
    return unicodedata.normalize("NFKC", text or "").strip().lower()

class PlayerMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
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

monitor = PlayerMonitor()
player = xbmc.Player()

def hms_to_seconds(hms):
    h, m, s = hms.strip().split(":")
    return int(h)*3600 + int(m)*60 + float(s)

def get_video_file():
    try:
        if not player.isPlayingVideo():
            return None
        path = player.getPlayingFile()
    except RuntimeError:
        return None

    log(f"🎯 Kodi playback path: {path}")
    log(f"🔧 enable_for_movies: {get_addon().getSettingBool('enable_for_movies')}")
    log(f"🔧 enable_for_tv_episodes: {get_addon().getSettingBool('enable_for_tv_episodes')}")

    if xbmcvfs.exists(path):
        return path

    log(f"❓ Unrecognized or inaccessible path: {path}")
    return None

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

def should_show_missing_file_toast(_):
    log("🚦 Entered should_show_missing_file_toast()")

    addon = xbmcaddon.Addon()  # ⚠ Dynamic access — avoid cached settings
    enable_for_movies = addon.getSetting("enable_for_movies").strip().lower() == "true"
    enable_for_tv_episodes = addon.getSetting("enable_for_tv_episodes").strip().lower() == "true"
    always_show = addon.getSetting("always_show_missing_toast").strip().lower() == "true"

    query_active = {
        "jsonrpc": "2.0",
        "id": "getPlayers",
        "method": "Player.GetActivePlayers"
    }
    response_active = xbmc.executeJSONRPC(json.dumps(query_active))
    active_result = json.loads(response_active)
    active_players = active_result.get("result", [])

    if not active_players:
        xbmc.sleep(250)
        retry_response = xbmc.executeJSONRPC(json.dumps(query_active))
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
    response_item = xbmc.executeJSONRPC(json.dumps(query_item))
    item_result = json.loads(response_item)
    item = item_result.get("result", {}).get("item", {})

    if not item or "title" not in item:
        log("⚠ Player.GetItem returned empty or missing title — metadata not ready")
        return False, {}

    playback_type = infer_playback_type(item)
    log(f"🔍 Playback type inferred: {playback_type}")

    log(f"🧮 enable_for_movies (raw): '{addon.getSetting('enable_for_movies')}'")
    log(f"🧮 enable_for_tv_episodes (raw): '{addon.getSetting('enable_for_tv_episodes')}'")
    log(f"🧮 always_show_missing_toast (raw): '{addon.getSetting('always_show_missing_toast')}'")

    if always_show:
        log("📢 Forcing toast display due to always_show_missing_toast = true")
        return True, item

    if playback_type == "movie" and not enable_for_movies:
        log("🛑 Suppressing toast — movie playback and disabled in settings")
        return False, item
    if playback_type == "episode" and not enable_for_tv_episodes:
        log("🛑 Suppressing toast — episode playback and disabled in settings")
        return False, item

    return True, item
def parse_chapters(video_path):
    base = os.path.splitext(video_path)[0]
    suffixes = ["-chapters.xml", "_chapters.xml"]
    fallback_base = None

    try:
        if player.isPlayingVideo():
            fallback_base = player.getPlayingFile().rsplit('.', 1)[0]
    except RuntimeError:
        log("⚠️ getPlayingFile() failed inside parse_chapters fallback")

    paths_to_try = [f"{base}{s}" for s in suffixes]
    if fallback_base:
        paths_to_try += [f"{fallback_base}{s}" for s in suffixes]

    xml_data = safe_file_read(*paths_to_try)
    if not xml_data:
        return None
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
    except RuntimeError:
        log("⚠️ getPlayingFile() failed inside parse_edl fallback")

    paths_to_try = [f"{base}.edl"]
    if fallback_base:
        paths_to_try.append(f"{fallback_base}.edl")

    edl_data = safe_file_read(*paths_to_try)
    if not edl_data:
        return []

    log(f"🧾 Raw EDL content:\n{edl_data}")
    segments = []
    mapping = get_edl_type_map()
    try:
        for line in edl_data.splitlines():
            parts = line.strip().split()
            if len(parts) == 3:
                s, e, action = float(parts[0]), float(parts[1]), int(parts[2])
                label = mapping.get(action, "segment")
                segments.append(SegmentItem(s, e, label, source="edl"))
                log(f"📦 Parsed EDL line: {s} → {e} | action={action} | label='{label}'")
    except Exception as e:
        log(f"❌ EDL parse failed: {e}")
    log(f"✅ Total segments parsed from EDL: {len(segments)}")
    return segments

def parse_segments(path):
    parsed = parse_chapters(path)
    if parsed:
        return parsed
    return parse_edl(path) or []

log_always("📡 XML-EDL Intro Skipper service started.")
while not monitor.abortRequested():
    if player.isPlayingVideo() or xbmc.getCondVisibility("Player.HasVideo"):
        video = get_video_file()
        if not video:
            monitor.last_video = None

        if video and video != monitor.last_video:
            monitor.last_video = video
            monitor.shown_missing_file_toast = False
            monitor.current_segments = parse_segments(video) or []
            monitor.prompted.clear()
            monitor.recently_dismissed.clear()
            monitor.playback_ready = False
            monitor.play_start_time = time.time()
            monitor.last_time = 0
            monitor.last_toast_time = 0  # 🧼 Reset cooldown when new video starts
            log(f"📺 New video: {video}, segments: {len(monitor.current_segments)}")
            log(f"🔍 Segment labels: {[s.segment_type_label for s in monitor.current_segments]}")

        try:
            current_time = player.getTime()
            log(f"🧪 Current playback time: {current_time}")
        except RuntimeError:
            log("⚠ player.getTime() failed — no media playing")
            continue

        if not monitor.playback_ready and current_time > 0:
            monitor.playback_ready = True
            monitor.playback_ready_time = time.time()
            log("✅ Playback confirmed via getTime() — setting playback_ready = True")

        if (
            monitor.playback_ready
            and not monitor.shown_missing_file_toast
            and time.time() - monitor.playback_ready_time >= 2
            and not monitor.current_segments
        ):
            log("⚠ [TOAST BLOCK] Entered toast logic block")
            try:
                allow_toast, item = should_show_missing_file_toast(None)
                if allow_toast:
                    cooldown = 6
                    now = time.time()
                    if now - monitor.last_toast_time >= cooldown:
                        playback_type = infer_playback_type(item)
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
                    log("✅ [TOAST BLOCK] Toast suppressed by playback type check")
            except Exception as e:
                log(f"❌ [TOAST BLOCK] should_show_missing_file_toast() failed: {e}")

            monitor.shown_missing_file_toast = True

        rewind_threshold = get_addon().getSettingInt("rewind_threshold_seconds")
        if current_time < monitor.last_time and monitor.last_time - current_time > rewind_threshold:
            log(f"⏪ Significant rewind detected ({monitor.last_time:.2f} → {current_time:.2f}) — threshold: {rewind_threshold}s")
            monitor.prompted.clear()
            monitor.recently_dismissed.clear()
            log("🧹 recently_dismissed cleared due to rewind")

        monitor.last_time = current_time

        if not monitor.playback_ready:
            log("⏳ Playback not ready — waiting before processing segments")
            continue

        for segment in monitor.current_segments:
            seg_id = (int(segment.start_seconds), int(segment.end_seconds))
            log(f"🔍 Checking segment {seg_id} at time {current_time:.2f}")

            if seg_id in monitor.prompted:
                log(f"⏭ Segment {seg_id} already prompted — skipping")
                continue
            if seg_id in monitor.recently_dismissed:
                log(f"🙅 Segment {seg_id} is in recently_dismissed — skipping")
                continue
            if not segment.is_active(current_time):
                continue
            if current_time > segment.end_seconds + 1.0:
                continue

            log(f"🔎 Raw segment label before skip mode check: '{segment.segment_type_label}'")

            behavior = get_user_skip_mode(segment.segment_type_label)
            if behavior == "never":
                log(f"🚫 Skipping dialog for '{segment.segment_type_label}' (user preference: never)")
                continue

            log(f"🕒 Active segment: {segment.segment_type_label} [{segment.start_seconds}-{segment.end_seconds}] → {behavior}")
            if behavior == "auto":
                player.seekTime(segment.end_seconds + 1.0)
                monitor.last_time = segment.end_seconds + 1.0
                monitor.prompted.add(seg_id)
                xbmcgui.Dialog().notification("Skipped", f"{segment.segment_type_label.title()} skipped", time=2000)
                log(f"⚡ Auto-skipped to {segment.end_seconds + 1.0}")
            elif behavior == "ask":
                if not player.isPlayingVideo():
                    log("⚠ Playback not active — skipping dialog")
                    continue

                try:
                    log("🛑 Debouncing skip dialog for 300ms")
                    xbmc.sleep(300)

                    layout_value = get_addon().getSetting("skip_dialog_position").replace(" ", "")
                    dialog_name = f"SkipDialog_{layout_value}.xml"
                    full_path = f"{get_addon().getAddonInfo('path')}/resources/skins/default/720p/{dialog_name}"

                    if not xbmcvfs.exists(full_path):
                        log(f"⚠ Dialog layout not found: {dialog_name} — falling back to SkipDialog.xml")
                        dialog_name = "SkipDialog.xml"

                    log(f"🎬 Showing skip dialog for: {segment.segment_type_label} → layout={dialog_name}")
                    dialog = SkipDialog(dialog_name, get_addon().getAddonInfo("path"), "default", "720p")
                    dialog.segment = segment
                    dialog.doModal()
                    confirmed = getattr(dialog, "response", None)
                    del dialog

                    if confirmed:
                        monitor.prompted.add(seg_id)
                        player.seekTime(segment.end_seconds + 1.0)
                        monitor.last_time = segment.end_seconds + 1.0
                        xbmcgui.Dialog().notification("Skipped", f"{segment.segment_type_label.title()} skipped", time=2000)
                        log(f"✅ User confirmed skip to {segment.end_seconds + 1.0}")
                    else:
                        log(f"🚫 User declined skip — adding {seg_id} to recently_dismissed")
                        monitor.recently_dismissed.add(seg_id)
                except Exception as e:
                    log(f"❌ Skip dialog failed: {e}")
            break

    if monitor.waitForAbort(CHECK_INTERVAL):
        break

