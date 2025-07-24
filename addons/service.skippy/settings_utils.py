import html
import unicodedata
import xml.etree.ElementTree as ET
import xbmcaddon
import xbmc
import xbmcvfs

def get_addon():
    return xbmcaddon.Addon()

def log(msg):
    if get_addon().getSettingBool("enable_verbose_logging"):
        xbmc.log(f"[{get_addon().getAddonInfo('id')} - SettingsUtils] {msg}", xbmc.LOGINFO)

def log_always(msg):
    xbmc.log(f"[{get_addon().getAddonInfo('id')} - SettingsUtils] {msg}", xbmc.LOGINFO)

def normalize_label(label):
    return unicodedata.normalize("NFKC", label or "").strip().lower()

def get_user_skip_mode(label):
    title = normalize_label(label)
    log(f"🔍 Determining skip mode for: '{title}'")

    def parse_setting(key):
        raw = get_addon().getSetting(key)
        return set(normalize_label(x) for x in raw.split(",") if x.strip())

    always = parse_setting("segment_always_skip")
    ask = parse_setting("segment_ask_skip")
    never = parse_setting("segment_never_skip")

    if title in always:
        log(f"⚡ Matched in 'always' list: {title}")
        return "auto"
    if title in ask:
        log(f"❓ Matched in 'ask' list: {title}")
        return "ask"
    if title in never:
        log(f"🚫 Matched in 'never' list: {title}")
        return "never"

    log(f"🕳️ No skip mode match found for: {title} → using default: ask")
    return "ask"

def get_edl_type_map():
    raw = get_addon().getSetting("edl_action_mapping")
    log(f"🔁 Raw EDL mapping string: {raw}")
    pairs = [entry.strip() for entry in raw.split(",") if ":" in entry]
    mapping = {}
    for pair in pairs:
        try:
            action, label = pair.split(":", 1)
            action_int = int(action.strip())
            normalized_label = normalize_label(label)
            mapping[action_int] = normalized_label
            log(f"✅ Parsed mapping: {action_int} → '{normalized_label}'")
        except Exception as e:
            log(f"⚠️ Skipped invalid mapping '{pair}': {e}")
    return mapping
