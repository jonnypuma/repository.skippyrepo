import xbmcgui
import xbmc
import xbmcaddon
import threading
import time
import json

def get_addon():
    return xbmcaddon.Addon()

def log(msg):
    if get_addon().getSettingBool("enable_verbose_logging"):
        xbmc.log(f"[{get_addon().getAddonInfo('id')} - SkipDialog] {msg}", xbmc.LOGINFO)

def log_always(msg):
    xbmc.log(f"[{get_addon().getAddonInfo('id')} - SkipDialog] {msg}", xbmc.LOGINFO)

class SkipDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.segment = kwargs.get("segment", None)
        log(f"📦 Loaded dialog layout: {args[0]}")

    def onInit(self):
        log_always(f"🔍 onInit called — segment={getattr(self, 'segment', None)}")

        if not hasattr(self, "segment") or not self.segment:
            log("❌ Segment not set — aborting dialog init")
            self.close()
            return

        duration = int(self.segment.end_seconds - self.segment.start_seconds)
        m, s = divmod(duration, 60)
        duration_str = f"{m}m{s}s" if m else f"{s}s"
        label = f"Skip {self.segment.segment_type_label.title()} ({duration_str})"
        self.getControl(3012).setLabel(label)
        self.setProperty("countdown", "")
        self._closing = False
        self.response = None
        self.player = xbmc.Player()
        self._total_duration = self.segment.end_seconds - self.segment.start_seconds
        self._start_time = time.time()

        # 🔧 Load progress bar setting
        try:
            raw = get_addon().getSetting("show_progress_bar").lower()
            self._show_progress = json.loads(raw)
        except Exception:
            self._show_progress = True
            log("⚠️ Failed to parse show_progress_bar setting — defaulting to True")

        log(f"🧩 show_progress_bar setting: {self._show_progress}")

        # 📊 Setup progress bar
        try:
            progress = self.getControl(3014)
            progress.setVisible(self._show_progress)
            if self._show_progress:
                progress.setPercent(0)
                log("📊 Progress bar initialized at 0%")
        except Exception as e:
            log(f"⚠️ Progress bar control error: {e}")

        log(f"🟦 Dialog initialized: segment='{self.segment.segment_type_label}', duration={duration_str}")
        threading.Thread(target=self._monitor_segment_end, daemon=True).start()

    def _monitor_segment_end(self):
        delay = 0.25
        timeout = 30  # Max dialog duration fallback

        while not self._closing:
            if not self.player.isPlaying():
                log("⏹️ Playback stopped during dialog")
                break

            current = self.player.getTime()
            remaining = int(self.segment.end_seconds - current)
            m, s = divmod(max(remaining, 0), 60)
            self.setProperty("countdown", f"{m}m{s}s" if m else f"{s}s")

            # 📊 Update progress bar
            if self._show_progress:
                try:
                    elapsed = max(current - self.segment.start_seconds, 0)
                    percent = int((elapsed / self._total_duration) * 100)
                    percent = min(max(percent, 0), 100)
                    self.getControl(3014).setPercent(percent)
                except Exception as e:
                    log(f"⚠️ Progress bar update error: {e}")

            # ⌛ Segment end reached
            if current >= self.segment.end_seconds - 0.5:
                log("⌛ Segment ended — auto-decline")
                self._closing = True
                self.response = False
                self.close()
                break

            # ⏳ Timeout fallback
            if time.time() - self._start_time > timeout:
                log("⏳ Timeout reached — auto-decline")
                self._closing = True
                self.response = False
                self.close()
                break

            time.sleep(delay)

    def onClick(self, controlId):
        self.response = (controlId == 3012)
        self._closing = True
        log(f"🖱️ User clicked: {controlId} → {'confirmed skip' if self.response else 'declined skip'}")
        self.close()

    def onAction(self, action):
        if action.getId() in [10, 92, 216]:
            log(f"🔙 User cancelled via action ID {action.getId()}")
            self.response = False
            self._closing = True
            self.close()

    def onClose(self):
        try:
            if self._show_progress:
                self.getControl(3014).setPercent(0)
                log("🔄 Progress bar reset on close")
        except Exception as e:
            log(f"⚠️ Error resetting progress bar on close: {e}")
