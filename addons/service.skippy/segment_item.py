import xbmc
import xbmcaddon
import unicodedata

ADDON = xbmcaddon.Addon()

def log(msg):
    if ADDON.getSettingBool("enable_verbose_logging"):
        xbmc.log(f"[{ADDON.getAddonInfo('id')} - SegmentItem] {msg}", xbmc.LOGINFO)

def log_always(msg):
    xbmc.log(f"[{ADDON.getAddonInfo('id')} - SegmentItem] {msg}", xbmc.LOGINFO)

def normalize_label(text):
    return unicodedata.normalize("NFKC", text or "").strip().lower()

class SegmentItem:
    def __init__(self, start_seconds, end_seconds, label="segment", source="edl"):
        self.start_seconds = start_seconds
        self.end_seconds = end_seconds
        self.source = source
        self.segment_type_label = normalize_label(label)
        log(f"🧩 New SegmentItem created: {self}")

    def is_active(self, current_time):
        active = self.start_seconds <= current_time <= self.end_seconds
        log(f"⏱️ Checking is_active: time={current_time:.2f}, segment=({self.start_seconds}-{self.end_seconds}) → {active}")
        return active

    def get_duration(self):
        duration = self.end_seconds - self.start_seconds
        log(f"📏 Duration of {self}: {duration:.2f}s")
        return duration

    def __str__(self):
        return f"{self.segment_type_label} [{self.start_seconds}-{self.end_seconds}] ({self.source})"
