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
    # Normalize and lowercase labels for consistent matching
    return unicodedata.normalize("NFKC", text or "").strip().lower()

class SegmentItem:
    def __init__(self, start_seconds, end_seconds, label="segment", source="edl", action_type=None, timeout=5.0, allow_input=True):
        if end_seconds < start_seconds:
            raise ValueError(f"Segment end time ({end_seconds}) must be after start time ({start_seconds})")

        self.start_seconds = start_seconds
        self.end_seconds = end_seconds
        self.source = source
        self.segment_type_label = normalize_label(label)
        self.action_type = normalize_label(action_type) if action_type else None
        self.timeout = timeout
        self.allow_input = allow_input

        log(f"🧩 New SegmentItem created: {self}")

    def is_active(self, current_time):
        # Check if current time falls within segment bounds
        active = self.start_seconds <= current_time <= self.end_seconds
        log(f"⏱️ Checking is_active: time={current_time:.2f}, segment=({self.start_seconds}-{self.end_seconds}) → {active}")
        return active

    def get_duration(self):
        # Return duration of the segment
        duration = self.end_seconds - self.start_seconds
        log(f"📏 Duration of {self}: {duration:.2f}s")
        return duration

    def to_dict(self):
        # Convert segment to dictionary format
        result = {
            "start": self.start_seconds,
            "end": self.end_seconds,
            "label": self.segment_type_label,
            "source": self.source,
            "action_type": self.action_type
        }
        log(f"📦 Converted SegmentItem to dict: {result}")
        return result

    def __str__(self):
        action = f", action={self.action_type}" if self.action_type else ""
        return f"{self.segment_type_label} [{self.start_seconds}-{self.end_seconds}] ({self.source}{action})"

# 🔍 Dialog trigger logic — stateless, no caching
def should_show_skip_dialog(current_time, segments, last_shown_times, debounce_seconds=5):
    for segment in segments:
        if segment.start_seconds <= current_time <= segment.end_seconds:
            segment_id = f"{segment.start_seconds}-{segment.end_seconds}"
            last_shown = last_shown_times.get(segment_id, 0)
            time_since_last = abs(current_time - last_shown)

            if time_since_last > debounce_seconds:
                last_shown_times[segment_id] = current_time
                log(f"📌 Triggering skip dialog for segment: {segment}")
                return segment
            else:
                log(f"⏳ Debounce active for segment {segment_id} — last shown {time_since_last:.2f}s ago")
    log("🔕 No eligible segment found for skip dialog at current time")
    return None

# Optional: Unit test block (can be moved to a separate test file)
if __name__ == "__main__":
    import unittest

    log_always("🧪 Running SegmentItem unit tests")

    class TestSegmentItem(unittest.TestCase):
        def test_valid_segment(self):
            seg = SegmentItem(10, 20, "intro", action_type="skip")
            self.assertEqual(seg.get_duration(), 10)
            self.assertTrue(seg.is_active(15))
            self.assertFalse(seg.is_active(25))
            self.assertEqual(seg.action_type, "skip")
            self.assertEqual(seg.timeout, 5.0)  # default value
            self.assertTrue(seg.allow_input)   # default value

        def test_invalid_segment(self):
            with self.assertRaises(ValueError):
                SegmentItem(30, 10, "bad")

        def test_to_dict(self):
            seg = SegmentItem(5, 15, "credits", "xml", "mute")
            expected = {
                "start": 5,
                "end": 15,
                "label": "credits",
                "source": "xml",
                "action_type": "mute"
            }
            self.assertEqual(seg.to_dict(), expected)

        def test_custom_timeout_and_input(self):
            seg = SegmentItem(0, 10, "ad", action_type="skip", timeout=8.0, allow_input=False)
            self.assertEqual(seg.timeout, 8.0)
            self.assertFalse(seg.allow_input)

    unittest.main()
