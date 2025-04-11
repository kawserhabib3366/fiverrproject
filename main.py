import customtkinter as ctk
from tkinter import messagebox, Menu, TclError, scrolledtext
import threading
import time
import os,sys
import pyautogui as pg
import pytesseract
from PIL import Image
import pygetwindow as gw
from datetime import datetime
import logging
from tkhtmlview import HTMLLabel, HTMLScrolledText
import requests

# ======================= CONFIGURATION =======================
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


SIDEBAR_IMAGE = resource_path('sidebar0.png')
MESSAGE_IMAGE = resource_path('msg1.png')
MESSAGE_IMAGE2 = resource_path('msg2.png')
TYPE_AREA_IMAGE = resource_path('typemsg.png')
SCREENSHOT_PATH = resource_path('screenshot.png')
MSGAGAIN = resource_path('msgagain.png')
OUTPUT_FILE = 'output.txt'
LOG_FILE = 'automation_log.txt'
CONFIDENCE = 0.75
WAIT_SHORT = 1
WAIT_MEDIUM = 2
WAIT_LONG = 3
BROWSER_TITLE = "Chrome"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# ======================= THEME SETUP =======================
ctk.set_appearance_mode("light")  # Force light theme
ctk.set_default_color_theme("blue")  # Set a light-friendly color theme

# ======================= LOGGER SETUP =======================
logging.basicConfig(
    level=logging.INFO,
    format="[{asctime}] [{levelname}] {message}",
    style="{",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================= GUI LOG HANDLER =======================
class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        try:
            self.text_widget.configure(state="normal")
            self.text_widget.insert("end", msg + "\n")
            self.text_widget.configure(state="disabled")
            self.text_widget.see("end")
        except (TclError, RuntimeError):
            pass  # Widget has been destroyed or is unavailable

# ======================= UTILITY FUNCTIONS =======================
def safe_wait(seconds=WAIT_SHORT, stop_event: threading.Event = None):
    """Wait in small increments, checking for a stop event."""
    end_time = time.time() + seconds
    while time.time() < end_time:
        if stop_event and stop_event.is_set():
            break
        time.sleep(0.1)

def wait_and_locate(image_path, confidence=CONFIDENCE, timeout=10, sidebarflat=False, stop_event: threading.Event = None):
    """Locate an image on the screen within a timeout period."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if stop_event and stop_event.is_set():
            raise Exception("Operation halted by user during image search.")
        conf = 0.55 if sidebarflat else confidence
        logger.info(f"Searching image '{image_path}' with confidence {conf}")
        location = pg.locateCenterOnScreen(image_path, confidence=conf)
        if location:
            return location
        time.sleep(0.5)
    raise TimeoutError(f"Image '{image_path}' not found within {timeout} seconds.")

def search_and_click(image, confidence=CONFIDENCE, timeout=15, after_wait=WAIT_MEDIUM, 
                     msgoragainflag=False, sideflag=False, stop_event: threading.Event = None):
    """Locate an image on the screen and click it."""
    try:
        location = wait_and_locate(image, confidence=confidence, timeout=timeout, sidebarflat=sideflag, stop_event=stop_event)
        pg.moveTo(location, duration=1)
        pg.click()
        safe_wait(after_wait, stop_event)
        logger.info(f"Clicked element: {image}")
    except Exception as error:
        logger.error(f"Failed to click image '{image}': {error}")
        if msgoragainflag:
            try:
                location = wait_and_locate(MSGAGAIN, confidence=confidence, timeout=timeout, stop_event=stop_event)
                pg.moveTo(location, duration=1)
                safe_wait(after_wait, stop_event)
                logger.info(f"Already sent message for: {image}")
                return True
            except Exception as inner_error:
                logger.error(f"Error handling 'msg again' for '{image}': {inner_error}")
                raise
        else:
            raise

def extract_info(image_path):
    """Extract seller and item details from a screenshot."""
    try:
        image = Image.open(image_path)
    except Exception as e:
        logger.error(f"Unable to open image '{image_path}': {e}")
        return {"person_name": None, "item_name": None}
    text = pytesseract.image_to_string(image)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        if line.startswith("Message "):
            person_name = line.replace("Message ", "").strip()
            item_name = lines[idx+1].strip() if idx+1 < len(lines) else None
            return {"person_name": person_name, "item_name": item_name}
    return {"person_name": None, "item_name": None}

def save_info(info):
    """Save extracted details to the output file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(OUTPUT_FILE, "a") as file:
        file.write(f"Timestamp    : {timestamp}\n")
        file.write(f"Seller Name  : {info.get('person_name')}\n")
        file.write(f"Product Title: {info.get('item_name')}\n")
        file.write("-" * 30 + "\n")
    logger.info(f"Recorded info: {info}")

# ======================= MARKETPLACE BOT =======================
class MarketplaceBot:
    def __init__(self, user_message, message_count, stop_event: threading.Event):
        self.user_message = user_message
        self.message_count = message_count
        self.stop_event = stop_event

    def adjust_browser(self):
        try:
            browser = gw.getWindowsWithTitle(BROWSER_TITLE)[0]
            logger.info("Adjusting browser window.")
            browser.minimize(); safe_wait(0.5, self.stop_event)
            browser.restore(); safe_wait(0.5, self.stop_event)
            browser.maximize(); safe_wait(1, self.stop_event)
            browser.activate(); safe_wait(0.5, self.stop_event)
            pg.press('f11'); safe_wait(WAIT_MEDIUM, self.stop_event)
        except IndexError:
            logger.error(f"Browser titled '{BROWSER_TITLE}' not found.")
            raise

    def preprocess_sidebar(self):
        try:
            logger.info("Locating sidebar...")
            loc = wait_and_locate(SIDEBAR_IMAGE, sidebarflat=True, stop_event=self.stop_event)
            pg.moveTo(loc); safe_wait(0.5, self.stop_event)
            pg.moveRel(310, 0, duration=0.5); pg.click(); safe_wait(WAIT_SHORT, self.stop_event)
            logger.info("Sidebar activated.")
        except Exception as e:
            logger.error(f"Sidebar error: {e}")
            raise

    def handle_message_flow(self):
        try:
            logger.info("Starting message flow.")
            pg.press('tab'); safe_wait(0.5, self.stop_event)
            pg.press('enter'); safe_wait(WAIT_LONG, self.stop_event)
            if search_and_click(MESSAGE_IMAGE, msgoragainflag=True, stop_event=self.stop_event):
                logger.info("Message already sent.")
                pg.press('esc'); safe_wait(1.5, self.stop_event)
                return
            pg.screenshot(SCREENSHOT_PATH)
            if not os.path.exists(SCREENSHOT_PATH): 
                raise FileNotFoundError("Screenshot failed.")
            info = extract_info(SCREENSHOT_PATH)
            logger.info(f"Extracted: {info}")
            save_info(info)
            search_and_click(TYPE_AREA_IMAGE, stop_event=self.stop_event)
            safe_wait(0.5, self.stop_event)
            pg.typewrite(self.user_message, interval=0.05)
            logger.info("Typed message.")
            safe_wait(1, self.stop_event)
            search_and_click(MESSAGE_IMAGE2, stop_event=self.stop_event)
            safe_wait(2.5, self.stop_event)
            safe_wait(1.5, self.stop_event)
            for _ in range(3):
                pg.press('esc'); safe_wait(1.5, self.stop_event)
        except Exception as e:
            logger.error(f"Flow error: {e}")

    def check_condition_and_respond(self):
        logger.info("Checking sidebar presence...")
        try:
            wait_and_locate(SIDEBAR_IMAGE, timeout=5, sidebarflat=True, stop_event=self.stop_event)
            self.handle_message_flow()
        except Exception as e:
            logger.warning(f"Skip cycle: {e}")

    def resilient_main_loop(self):
        i = 0
        while i < self.message_count and not self.stop_event.is_set():
            logger.info(f"Iteration {i+1}/{self.message_count}")
            self.check_condition_and_respond()
            i += 1
            safe_wait(WAIT_MEDIUM, self.stop_event)
        logger.info("Automation ended." if self.stop_event.is_set() else "Completed all iterations.")

    def run_full_reset(self):
        try:
            self.adjust_browser()
            self.preprocess_sidebar()
        except Exception as e:
            logger.error(f"Init failed: {e}")
            return
        self.resilient_main_loop()

    def run_message_only(self):
        try:
            browser = gw.getWindowsWithTitle(BROWSER_TITLE)[0]
            safe_wait(1, self.stop_event)
            browser.activate()
            safe_wait(1.5, self.stop_event)
        except IndexError:
            logger.error("Browser not found for message-only mode.")
            raise
        self.resilient_main_loop()

# ======================= AUTOMATION GUI =======================
class AutomationGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Facebook Marketplace Automation")
        self.iconbitmap(resource_path("icon.ico"))
        self.geometry("640x580")
        self.resizable(True, True)
        self.stop_event = threading.Event()
        self.bot_thread = None  # Reference to the automation thread.
        self.create_widgets()
        self.create_menubar()  # Add the menu bar.
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        frame = ctk.CTkFrame(self, corner_radius=15)
        frame.pack(padx=30, pady=30, fill="both", expand=True)
        ctk.CTkLabel(frame, text="Facebook Marketplace Automation", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(10,20))
        ctk.CTkLabel(frame, text="Enter your message:").pack(anchor="w", padx=10)
        self.message_box = ctk.CTkTextbox(frame, width=500, height=120, font=("Segoe UI", 18))
        self.message_box.pack(pady=(5,20), expand=True)
        self.message_box.insert("1.0", "Is this item still available?")
        ctk.CTkLabel(frame, text="Number of iterations:").pack(anchor="w", padx=10)
        self.message_count_entry = ctk.CTkEntry(frame, placeholder_text="e.g. 5")
        self.message_count_entry.pack(pady=5)
        self.message_count_entry.insert(0, "5")
        self.status_label = ctk.CTkLabel(frame, text="Awaiting instructions...", text_color="#555")
        self.status_label.pack(pady=(30,10))
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=10)
        self.start_button_full = ctk.CTkButton(
            btn_frame, text="Start Automation (Full Reset)",
            command=self.start_full_reset,
            fg_color="#1a73e8", hover_color="#155ab6",
            width=180, height=40,
            font=("Segoe UI", 14, "bold")
        )
        self.start_button_full.grid(row=0, column=0, padx=5)
        self.start_button_msg = ctk.CTkButton(
            btn_frame, text="Automate Message Only",
            command=self.start_message_only,
            fg_color="#34a853", hover_color="#0f9d58",
            width=180, height=40,
            font=("Segoe UI", 14, "bold")
        )
        self.start_button_msg.grid(row=0, column=1, padx=5)
        ctk.CTkLabel(frame, text="© 2025 by KAWSER HABIB", font=("Segoe UI", 5), text_color="#aaa").pack(pady=(20,0))

    def create_menubar(self):
        """Create a menu bar with a Help > Documentation option."""
        menubar = Menu(self)
        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="Documentation", command=self.show_documentation)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=menubar)



    def show_documentation(self):
        """Open a new window with user documentation rendered in HTML."""
        doc_window = ctk.CTkToplevel(self)
        doc_window.title("Documentation")
        doc_window.geometry("650x600")
        doc_window.attributes('-topmost', True)

        html_content = """
        <h2>Facebook Marketplace Automation</h2>
        <h3>Overview:</h3>
        <p>This application automates sending messages via Facebook Marketplace by interacting with your browser and using image recognition. This ensures <b> bot detection by Facebook </b> is avoided, keeping your <b>account safe</b>.</p>
        
        <h3>How to Use:</h3>
        <ol>
            <li>Enter the message text in the <b>'Enter your message'</b> field.</li>
            <li>Specify the number of iterations in the <b>'Number of iterations'</b> field.</li>
            <li>Click <b>'Start Automation (Full Reset)'</b> or <b>'Automate Message Only'</b> to begin.</li>
        </ol>
        <p><h4>Full Reset</h4>: Adjusts the browser and starts from the <b>first listing.</b><br>
        <h4>Message Only</h4>: Sends messages from your <b>selected listing.</b> select the previous item<br>
        <i>Tip:</i> Use the <b>Tab key</b> to focus the item.</p>

        <h3>During Automation:</h3>
        <ul>
            <li>Status window shows real-time progress.</li>
            <li>Click <b>'Stop Automation'</b> to stop anytime.</li>
        </ul>

        <h3>Logs:</h3>
        <p>Details log saved in  <code>output.txt</code>.</p>
        <p>Logs are saved in the GUI and in <code>automation_log.txt</code>.</p>

        <h3>Notes:</h3>
        <ul>
            <li><b>DO NOT USE INTERFERE WHILE AUTOMATION RUNNING</b></li>
            <li>DO NOT USE YOUR KEYBOARD OR MOUSE DURING AUTOMATION</li>
        </ul>

        <p>Need help? Contact the developer. feel free to reach out:</p>
        <ul>
            <li>📧 Gmail: <i>kawserhabib3366@gmail.com</i></li>
            <li>📱 WhatsApp: <i>+880 1957-333030</i></li>
        </ul>
        """

        html_view = HTMLScrolledText(doc_window, html=html_content, width=400, height=400)
        html_view.pack(fill="both", expand=True, padx=10, pady=10)



    def show_bot_window(self):
        self.bot_window = ctk.CTkToplevel(self)
        self.bot_window.title("Automation in Progress")

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Window size
        window_width = 200
        window_height = 200

        # Position for bottom right
        x = screen_width - window_width-200
        y = screen_height - window_height -200

        self.bot_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.bot_window.resizable(False, False)
        self.bot_window.attributes('-topmost', True)
        ctk.CTkLabel(self.bot_window, text="Automation Running...", font=ctk.CTkFont(size=11, weight="bold")).pack(pady=1)
        ctk.CTkButton(self.bot_window, text="Stop Automation", fg_color="#e53935", hover_color="#c62828", command=self.quit_bot).pack(pady=2)
        log_frame = ctk.CTkFrame(self.bot_window, corner_radius=8)
        log_frame.pack(padx=1, pady=1, fill="both", expand=True)
        ctk.CTkLabel(log_frame, text="Automation Log:", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=1, pady=(1,0))
        self.log_text_widget = ctk.CTkTextbox(log_frame, width=60, height=30, font=("Segoe UI", 8))
        self.log_text_widget.pack(padx=1, pady=1, fill="both", expand=True)
        self.log_text_widget.configure(state="disabled")
        self.remove_text_handler()  # Clean up before adding.
        self.text_handler = TextHandler(self.log_text_widget)
        self.text_handler.setFormatter(logging.Formatter("[{asctime}] [{levelname}] {message}", style="{"))
        logger.addHandler(self.text_handler)

    def remove_text_handler(self):
        # Remove existing TextHandler instances, if any.
        for handler in logger.handlers[:]:
            if isinstance(handler, TextHandler):
                logger.removeHandler(handler)

    def update_status(self, message, color="#555"):
        self.status_label.configure(text=message, text_color=color)

    def disable_controls(self):
        self.start_button_full.configure(state="disabled")
        self.start_button_msg.configure(state="disabled")

    def enable_controls(self):
        self.start_button_full.configure(state="normal")
        self.start_button_msg.configure(state="normal")
        self.update_status("Awaiting instructions...", "#555")
        self.deiconify()

    def start_full_reset(self):
        self.start_bot(run_type="full")

    def start_message_only(self):
        self.start_bot(run_type="msg")

    def start_bot(self, run_type):
        
        # Check internet connection
        try:
            requests.get("https://www.google.com", timeout=3)
        except requests.ConnectionError:
            messagebox.showerror("No Internet", "Internet connection is required to run the bot.")
            return

        # Check permission from remote file
        try:
            response = requests.get("https://ddom.web.app/fma.txt", timeout=5)
            if response.text.strip().lower() != "allow":
                messagebox.showwarning("Blocked", "Bot usage is currently not allowed by the server.")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to verify bot permission:\n{e}")
            return
        if not os.path.exists(TESSERACT_PATH):
            messagebox.showerror("Tesseract Not Found", f"Tesseract executable was not found at:\n{TESSERACT_PATH}")
            return

        # Reset the stop event before starting a new automation run.
        self.stop_event.clear()

        user_message = self.message_box.get("1.0", "end").strip()
        if not user_message:
            messagebox.showwarning("Missing Message", "Please enter a message before starting the automation.")
            return

        try:
            message_count = int(self.message_count_entry.get())
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid number for message iterations.")
            return

        self.disable_controls()
        self.update_status("Initializing automation...", "#ffaa00")
        self.withdraw()
        self.show_bot_window()

        bot = MarketplaceBot(user_message, message_count, self.stop_event)
        target = bot.run_full_reset if run_type == "full" else bot.run_message_only
        self.bot_thread = threading.Thread(target=target, daemon=True)
        self.bot_thread.start()

    def quit_bot(self):
        # Signal the automation to stop.
        self.stop_event.set()
        logger.info("User requested stop.")
        self.remove_text_handler()
        self.enable_controls()
        if hasattr(self, 'bot_window'):
            self.bot_window.destroy()

    def on_close(self):
        logger.info("Application closing.")
        self.stop_event.set()  # Ensure any running process stops.
        self.destroy()

if __name__ == "__main__":
    app = AutomationGUI()
    app.mainloop()
