import xbmcgui
import xbmc
import xbmcaddon
import threading
import time
import json
import os

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

        # 🎨 Pre-set focus texture so XML can optionally read it
        focus_texture = get_addon().getSetting("skip_dialog_focus_texture") or "button_focus_blue.png"
        texture_path = xbmc.translatePath(f"special://skin/media/{focus_texture}")
        if not os.path.exists(texture_path):
            log(f"⚠️ Texture not found at {texture_path} — falling back to default")
            focus_texture = "button_focus_blue.png"
        else:
            log(f"🎨 Found focus texture: {texture_path}")

        self.setProperty("focus_texture", focus_texture)
        log(f"🎨 Pre-set focus texture property: {focus_texture}")

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

        log(f"🧠 Segment metadata: start={self.segment.start_seconds}, end={self.segment.end_seconds}, type={self.segment.segment_type_label}")

        # 🎯 Apply focus texture directly to buttons
        try:
            self.getControl(3012).setTexture(self.getProperty("focus_texture"), xbmcgui.CONTROL_FOCUS)
            self.getControl(3013).setTexture(self.getProperty("focus_texture"), xbmcgui.CONTROL_FOCUS)
            log(f"🎯 Focus texture applied directly to buttons: {self.getProperty('focus_texture')}")
        except Exception as e:
            log(f"⚠️ Failed to apply focus texture: {e}")

        # ⏭️ Set property for next segment jump time
        if self.segment.next_segment_start is not None:
            jump_m, jump_s = divmod(int(self.segment.next_segment_start), 60)
            jump_str = f"Skip to next segment at {jump_m:02d}:{jump_s:02d}"
            self.setProperty("next_jump_label", jump_str)
            self.setProperty("show_next_jump", "true")
            log(f"⏭️ Dialog configured for jump to next segment at {self.segment.next_segment_start}s")
        else:
            self.setProperty("show_next_jump", "false")
            log("➡️ Dialog configured for normal skip to end of segment")

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
        timeout = self._total_duration + 5

        while not self._closing:
            if not self.player.isPlaying():
                log("⏹️ Playback stopped during dialog")
                break

            current = self.player.getTime()
            remaining = int(self.segment.end_seconds - current)
            m, s = divmod(max(remaining, 0), 60)
            self.setProperty("countdown", f"{m:02d}:{s:02d}")

            if self._show_progress:
                try:
                    elapsed = max(current - self.segment.start_seconds, 0)
                    percent = int((elapsed / self._total_duration) * 100)
                    percent = min(max(percent, 0), 100)
                    self.getControl(3014).setPercent(percent)
                except Exception as e:
                    log(f"⚠️ Progress bar update error: {e}")

            if current >= self.segment.end_seconds - 0.5:
                log("⌛ Segment ended — auto-decline")
                self._closing = True
                self.response = False
                self.close()
                break

            if time.time() - self._start_time > timeout:
                log("⏳ Timeout reached — auto-decline")
                self._closing = True
                self.response = False
                self.close()
                break

            time.sleep(delay)

    def onClick(self, controlId):
        if controlId == 3012:
            self.response = self.segment.next_segment_start or self.segment.end_seconds
            log(f"🖱️ User clicked skip → skipping to {self.response}s")
        else:
            self.response = False
            log(f"🖱️ User clicked cancel/close → declining skip")

        self._closing = True
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
