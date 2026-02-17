"""
LLM Screen Automation Tool
===========================
A background tool that captures the screen, analyzes it with an LLM (via LM Studio),
identifies interactive UI elements, and moves/clicks the cursor automatically.

Hotkeys:
    Ctrl+M  -> Start automation (capture screen → analyze → move & click)
    Ctrl+;  -> Stop automation immediately

Prerequisites:
    - LM Studio running locally at http://localhost:1234
    - A vision-capable model loaded (e.g., gemma3:4b)
    - Python packages: openai, pyautogui, Pillow, keyboard, pystray
    - Administrator privileges (required for global hotkeys on Windows)

Usage:
    python llm_cursor_tool.py

Architecture:
    ┌───────────────┐     ┌──────────────┐     ┌─────────────────┐
    │ ScreenAnalyzer │────▶│ LM Studio API│────▶│ CursorController│
    │ (screenshot)   │     │ (analysis)   │     │ (move & click)  │
    └───────────────┘     └──────────────┘     └─────────────────┘
           ▲                                           │
           └──────────── AutomationEngine ─────────────┘
                    (orchestrates the loop)

Classes:
    ScreenAnalyzer    - Captures screen, encodes to base64, sends to LLM API
    CursorController  - Parses LLM coordinates, moves/clicks the mouse cursor
    AutomationEngine  - Runs the capture→analyze→click loop in a background thread
    HotkeyManager     - Registers global Ctrl+M / Ctrl+; hotkeys via keyboard lib
    TrayApp           - Creates a system tray icon with start/stop/quit menu
"""

# =============================================================================
# Standard library imports
# =============================================================================
import sys               # System-level operations (unused currently, reserved)
import threading         # Background thread for the automation loop
import time              # Sleep between automation cycles
import json              # Parse structured JSON responses from the LLM
import re               # Regex extraction of JSON from LLM text output
import io               # In-memory byte buffer for image encoding
import base64            # Encode screenshot images to base64 for the API
import logging           # Structured logging throughout the application

# =============================================================================
# Third-party imports
# =============================================================================
import pyautogui         # Screenshot capture and mouse/keyboard automation
import keyboard          # Global hotkey registration (Ctrl+M, Ctrl+;)
from PIL import Image, ImageDraw  # Image processing & tray icon creation
from openai import OpenAI         # OpenAI-compatible client for LM Studio
import pystray           # System tray icon for background operation

# =============================================================================
# Configuration Constants
# =============================================================================
# -- LM Studio connection --
LM_STUDIO_URL = "http://localhost:1234/v1"   # LM Studio local server endpoint
LM_STUDIO_API_KEY = "lm-studio"              # Default API key for LM Studio

# -- Screenshot settings --
SCREENSHOT_MAX_SIZE = (1280, 1280)  # Max dimensions to resize screenshots (px)
SCREENSHOT_QUALITY = 85             # JPEG quality (1-100, lower = smaller/faster)

# -- Automation timing --
ANALYSIS_INTERVAL = 3       # Seconds to wait between each automation cycle
CURSOR_MOVE_DURATION = 0.4  # Seconds for smooth cursor animation to target

# -- Logging --
LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"

# =============================================================================
# Logging Setup
# =============================================================================
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%H:%M:%S")
logger = logging.getLogger("LLM-Cursor-Tool")

# ---------------------------------------------------------------------------
# LLM Prompt
# ---------------------------------------------------------------------------
ANALYSIS_PROMPT = """You are a screen analysis assistant. Analyze this screenshot carefully.

Your tasks:
1. Describe briefly what is currently on screen (max 2 sentences).
2. Identify ALL clickable/interactive UI elements you can see (buttons, links, input fields, menu items, checkboxes, dropdowns, etc.).
3. For each element, estimate its CENTER pixel coordinates (x, y) on the screen.
4. Determine which element is the MOST RELEVANT or CORRECT option to interact with next (e.g., a primary action button, a "Next" button, an "OK/Submit" button, or the most logical next step).

Return your answer STRICTLY as JSON in the following format. Do NOT include any other text outside the JSON block:
{
  "screen_description": "Brief description of what's on screen",
  "elements": [
    {"label": "Element text/name", "x": 500, "y": 300, "type": "button"},
    {"label": "Another element", "x": 200, "y": 450, "type": "link"}
  ],
  "recommended": {
    "label": "The best element to click",
    "x": 500,
    "y": 300,
    "action": "click",
    "reason": "Why this is the correct choice"
  }
}
"""


# ===========================================================================
# ScreenAnalyzer — captures screen & sends to LLM
# ===========================================================================
class ScreenAnalyzer:
    """
    Captures the screen and sends it to LM Studio for vision-based analysis.

    This class handles the full pipeline of:
      1. Taking a screenshot via pyautogui
      2. Resizing and encoding it as a base64 JPEG string
      3. Sending it to the LM Studio API with a structured prompt
      4. Parsing the JSON response containing UI element coordinates

    Attributes:
        client (OpenAI): OpenAI-compatible API client connected to LM Studio.
    """

    def __init__(self):
        """Initialize the ScreenAnalyzer with a connection to LM Studio."""
        self.client = OpenAI(base_url=LM_STUDIO_URL, api_key=LM_STUDIO_API_KEY)

    # ---- helpers ----------------------------------------------------------
    @staticmethod
    def capture_screenshot() -> Image.Image:
        """
        Take a full screenshot of the primary display.

        Returns:
            Image.Image: A PIL Image object containing the screenshot.
        """
        return pyautogui.screenshot()

    @staticmethod
    def encode_image(image: Image.Image) -> str:
        """
        Resize and encode an image to a base64 JPEG string.

        The image is resized to fit within SCREENSHOT_MAX_SIZE while
        maintaining aspect ratio, then JPEG-compressed for efficient
        transmission to the LLM API.

        Args:
            image: The PIL Image to encode.

        Returns:
            str: Base64-encoded JPEG string ready for the API payload.
        """
        img = image.copy()
        img.thumbnail(SCREENSHOT_MAX_SIZE)  # Resize while keeping aspect ratio
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=SCREENSHOT_QUALITY)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    # ---- main analysis ----------------------------------------------------
    def analyze(self, image: Image.Image) -> dict | None:
        """
        Send a screenshot image to the LLM for analysis.

        Sends the image along with ANALYSIS_PROMPT to the LM Studio API.
        The LLM is expected to return a JSON object describing the screen
        contents, listing interactive elements with coordinates, and
        recommending the best element to click.

        Args:
            image: The screenshot as a PIL Image object.

        Returns:
            dict: Parsed JSON response with keys:
                  - screen_description (str)
                  - elements (list of dicts with label, x, y, type)
                  - recommended (dict with label, x, y, action, reason)
            None: If the request fails or the response can't be parsed.
        """
        b64 = self.encode_image(image)
        try:
            resp = self.client.chat.completions.create(
                model="model-identifier",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": ANALYSIS_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=600,
                temperature=0.1,
            )
            raw = resp.choices[0].message.content
            logger.info("LLM raw response:\n%s", raw)
            return self._parse_response(raw)

        except Exception as exc:
            logger.error("LLM request failed: %s", exc)
            return None

    # ---- JSON extraction --------------------------------------------------
    @staticmethod
    def _parse_response(raw: str) -> dict | None:
        """
        Extract and parse JSON from the LLM's raw text response.

        Attempts three parsing strategies in order:
          1. Direct JSON.loads() — if the response is pure JSON
          2. Markdown fence extraction — if wrapped in ```json ... ```
          3. Greedy regex match — finds the first { ... } block

        Args:
            raw: The raw text response from the LLM.

        Returns:
            dict: The parsed JSON object if successful.
            None: If no valid JSON could be extracted.
        """
        # Try direct JSON parse first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON block from markdown fences
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find any JSON object in the text
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse LLM response as JSON.")
        return None


# ===========================================================================
# CursorController — moves the cursor based on LLM output
# ===========================================================================
class CursorController:
    """
    Controls the mouse cursor based on coordinates from the LLM analysis.

    Provides methods to:
      - Move the cursor smoothly to a target position
      - Click, double-click, or right-click at that position
      - Execute the LLM's recommended action from the analysis JSON

    All coordinates are clamped to the screen bounds to prevent errors.
    """

    @staticmethod
    def move_and_click(x: int, y: int, action: str = "click"):
        """
        Smoothly move the cursor to (x, y) and perform a mouse action.

        Coordinates are clamped to stay within the screen boundaries.
        The cursor moves with a smooth animation over CURSOR_MOVE_DURATION.

        Args:
            x: Target X coordinate (pixels from left).
            y: Target Y coordinate (pixels from top).
            action: Mouse action — 'click', 'double_click', or 'right_click'.
                    Defaults to 'click' for unrecognized values.
        """
        screen_w, screen_h = pyautogui.size()

        # Clamp coordinates to screen bounds
        x = max(0, min(x, screen_w - 1))
        y = max(0, min(y, screen_h - 1))

        logger.info("Moving cursor to (%d, %d) — action: %s", x, y, action)
        pyautogui.moveTo(x, y, duration=CURSOR_MOVE_DURATION)

        if action == "click":
            pyautogui.click()
        elif action == "double_click":
            pyautogui.doubleClick()
        elif action == "right_click":
            pyautogui.rightClick()
        else:
            pyautogui.click()

    @staticmethod
    def execute(analysis: dict):
        """
        Execute the recommended action from the LLM's analysis result.

        Extracts the 'recommended' field from the analysis dict,
        validates that coordinates are present, logs the action,
        then calls move_and_click.

        Args:
            analysis: The parsed JSON dict from ScreenAnalyzer.analyze().
                      Must contain a 'recommended' key with 'x', 'y', 'action'.
        """
        rec = analysis.get("recommended")
        if not rec:
            logger.warning("No recommended action in LLM response.")
            return

        x = rec.get("x")
        y = rec.get("y")
        action = rec.get("action", "click")
        label = rec.get("label", "unknown")
        reason = rec.get("reason", "")

        if x is None or y is None:
            logger.warning("Recommended element has no coordinates.")
            return

        logger.info(
            ">> Recommended: '%s' at (%d, %d) — %s",
            label, x, y, reason,
        )
        CursorController.move_and_click(int(x), int(y), action)


# ===========================================================================
# AutomationEngine — the main loop
# ===========================================================================
class AutomationEngine:
    """
    The main automation engine that orchestrates the full workflow.

    Runs a continuous loop in a background thread:
      1. Capture a screenshot of the display
      2. Send it to the LLM for analysis via ScreenAnalyzer
      3. Parse the response and extract the recommended action
      4. Move the cursor and click via CursorController
      5. Wait ANALYSIS_INTERVAL seconds, then repeat

    The loop can be started/stopped via start() and stop() methods,
    which are triggered by hotkeys (Ctrl+M / Ctrl+;) or the tray menu.

    Attributes:
        analyzer (ScreenAnalyzer): Handles screen capture & LLM communication.
        controller (CursorController): Handles cursor movement & clicking.
        is_running (bool): Whether the automation loop is currently active.
    """

    def __init__(self):
        """Initialize the engine with analyzer, controller, and thread state."""
        self.analyzer = ScreenAnalyzer()
        self.controller = CursorController()
        self._running = False           # Flag to control the loop
        self._thread: threading.Thread | None = None  # Background worker thread

    # ---- public API -------------------------------------------------------
    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        """Start the automation loop in a background thread."""
        if self._running:
            logger.info("Automation is already running.")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("=== Automation STARTED (Ctrl+; to stop) ===")

    def stop(self):
        """Stop the automation loop."""
        if not self._running:
            logger.info("Automation is not running.")
            return
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("=== Automation STOPPED ===")

    # ---- internal loop ----------------------------------------------------
    def _loop(self):
        while self._running:
            try:
                # 1. Capture screen
                logger.info("Capturing screen...")
                screenshot = self.analyzer.capture_screenshot()

                # 2. Analyze with LLM
                logger.info("Sending to LLM for analysis...")
                analysis = self.analyzer.analyze(screenshot)

                if analysis:
                    desc = analysis.get("screen_description", "N/A")
                    elements = analysis.get("elements", [])
                    logger.info("Screen: %s", desc)
                    logger.info("Found %d interactive elements.", len(elements))

                    # 3. Execute recommended action
                    self.controller.execute(analysis)
                else:
                    logger.warning("No valid analysis returned. Retrying...")

            except Exception as exc:
                logger.error("Automation cycle error: %s", exc)

            # Wait before next cycle
            for _ in range(int(ANALYSIS_INTERVAL * 10)):
                if not self._running:
                    return
                time.sleep(0.1)


# ===========================================================================
# TrayApp — system tray icon with status
# ===========================================================================
class TrayApp:
    """
    System tray application for background operation.

    Displays a small icon in the Windows system tray:
      - Green circle  = automation is RUNNING
      - Red circle    = automation is STOPPED

    Right-click the icon for a menu with:
      - Start (Ctrl+M)
      - Stop  (Ctrl+;)
      - Quit

    Attributes:
        engine (AutomationEngine): Reference to the automation engine.
        icon (pystray.Icon): The system tray icon instance.
        ICON_SIZE (int): Size of the generated icon in pixels.
    """

    ICON_SIZE = 64  # Icon dimensions in pixels

    def __init__(self, engine: AutomationEngine):
        """Initialize with a reference to the automation engine."""
        self.engine = engine
        self.icon: pystray.Icon | None = None

    # ---- icon creation ----------------------------------------------------
    def _create_icon_image(self, color: str = "#4CAF50") -> Image.Image:
        """Create a simple colored circle icon."""
        img = Image.new("RGBA", (self.ICON_SIZE, self.ICON_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Outer circle
        draw.ellipse(
            [4, 4, self.ICON_SIZE - 4, self.ICON_SIZE - 4],
            fill=color,
            outline="#FFFFFF",
            width=2,
        )
        # Inner "AI" dot
        center = self.ICON_SIZE // 2
        draw.ellipse(
            [center - 8, center - 8, center + 8, center + 8],
            fill="#FFFFFF",
        )
        return img

    # ---- menu actions -----------------------------------------------------
    def _on_start(self, icon, item):
        self.engine.start()
        self._update_icon()

    def _on_stop(self, icon, item):
        self.engine.stop()
        self._update_icon()

    def _on_quit(self, icon, item):
        self.engine.stop()
        icon.stop()

    def _update_icon(self):
        if self.icon:
            if self.engine.is_running:
                self.icon.icon = self._create_icon_image("#4CAF50")  # green
                self.icon.title = "LLM Cursor Tool — RUNNING"
            else:
                self.icon.icon = self._create_icon_image("#F44336")  # red
                self.icon.title = "LLM Cursor Tool — STOPPED"

    # ---- run --------------------------------------------------------------
    def build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("▶  Start (Ctrl+M)", self._on_start),
            pystray.MenuItem("■  Stop  (Ctrl+;)", self._on_stop),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("✕  Quit", self._on_quit),
        )

    def run(self):
        self.icon = pystray.Icon(
            name="llm_cursor_tool",
            icon=self._create_icon_image("#F44336"),
            title="LLM Cursor Tool — STOPPED",
            menu=self.build_menu(),
        )
        self.icon.run()


# ===========================================================================
# HotkeyManager — global hotkeys
# ===========================================================================
class HotkeyManager:
    """
    Manages global keyboard hotkeys for controlling the automation.

    Registers two system-wide hotkeys:
      - Ctrl+M  : Start the automation engine
      - Ctrl+;  : Stop the automation engine

    These hotkeys work globally across all applications, even when
    this tool is running in the background. Requires administrator
    privileges on Windows.

    Attributes:
        engine (AutomationEngine): Reference to the automation engine to control.
    """

    def __init__(self, engine: AutomationEngine):
        """Initialize with a reference to the automation engine."""
        self.engine = engine

    def register(self):
        """
        Register global hotkeys with the operating system.

        Uses the 'keyboard' library to listen for key combinations.
        'suppress=True' prevents the hotkey from being passed to other apps.
        """
        keyboard.add_hotkey("ctrl+m", self._on_start, suppress=True)
        keyboard.add_hotkey("ctrl+;", self._on_stop, suppress=True)
        logger.info("Hotkeys registered: Ctrl+M (start), Ctrl+; (stop)")

    def _on_start(self):
        """Callback for Ctrl+M — starts the automation."""
        logger.info("Hotkey Ctrl+M pressed!")
        self.engine.start()

    def _on_stop(self):
        """Callback for Ctrl+; — stops the automation."""
        logger.info("Hotkey Ctrl+; pressed!")
        self.engine.stop()


# ===========================================================================
# Entry point
# ===========================================================================
def main():
    """
    Application entry point.

    Initializes all components (engine, hotkeys, tray), prints the
    welcome banner, and starts the system tray icon on the main thread.
    The application runs until the user quits via the tray menu.
    """
    # -- Welcome banner (displayed in console when run directly) --
    print(r"""
    ╔══════════════════════════════════════════════════════╗
    ║         LLM CURSOR AUTOMATION TOOL                  ║
    ║                                                     ║
    ║   Ctrl+M   →  Start screen analysis & auto-click    ║
    ║   Ctrl+;   →  Stop automation                       ║
    ║                                                     ║
    ║   Requires LM Studio running at localhost:1234      ║
    ║   with a vision-capable model loaded.               ║
    ╚══════════════════════════════════════════════════════╝
    """)

    # Disable pyautogui's built-in fail-safe (moving mouse to corner
    # won't abort the program). User can still stop with Ctrl+;
    pyautogui.FAILSAFE = False

    # -- Create core components --
    engine = AutomationEngine()       # The main automation loop
    hotkey_mgr = HotkeyManager(engine)  # Global hotkey listener
    tray = TrayApp(engine)            # System tray icon & menu

    # -- Register global hotkeys (Ctrl+M, Ctrl+;) --
    hotkey_mgr.register()

    # -- Start the system tray icon --
    # This blocks the main thread and keeps the application alive.
    # The automation runs in a separate daemon thread when activated.
    logger.info("System tray icon active. Right-click the tray icon for options.")
    tray.run()

    # -- Cleanup after tray is closed (user clicked Quit) --
    engine.stop()
    logger.info("Application exited.")


if __name__ == "__main__":
    main()
