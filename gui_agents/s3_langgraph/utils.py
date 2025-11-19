import re
import time
import json
import base64
import logging
from io import BytesIO
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

import pytesseract
from pytesseract import Output
from PIL import Image

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from gui_agents.s3.memory.procedural_memory import PROCEDURAL_MEMORY
from gui_agents.s3.utils.common_utils import create_pyautogui_code

logger = logging.getLogger("desktopenv.agent")

UBUNTU_APP_SETUP = """import subprocess;
import difflib;
import pyautogui;
pyautogui.press('escape');
time.sleep(0.5);
output = subprocess.check_output(['wmctrl', '-lx']);
output = output.decode('utf-8').splitlines();
window_titles = [line.split(None, 4)[2] for line in output];
closest_matches = difflib.get_close_matches('APP_NAME', window_titles, n=1, cutoff=0.1);
if closest_matches:
    closest_match = closest_matches[0];
    for line in output:
        if closest_match in line:
            window_id = line.split()[0]
            break;
subprocess.run(['wmctrl', '-ia', window_id])
subprocess.run(['wmctrl', '-ir', window_id, '-b', 'add,maximized_vert,maximized_horz'])
"""

SET_CELL_VALUES_CMD = """import uno
import subprocess
import unicodedata, json

def identify_document_type(component):
    if component.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        return "Calc"

    if component.supportsService("com.sun.star.text.TextDocument"):
        return "Writer"

    if component.supportsService("com.sun.star.sheet.PresentationDocument"):
        return "Impress"

    return None

def _norm_name(s: str | None) -> str | None:
    if s is None:
        return None
    if "\\\\u" in s or "\\\\U" in s or "\\\\x" in s:
        try:
            # json.loads handles all the escape forms safely
            s = json.loads(f"{{s}}")
        except Exception:
            # fallback: best-effort
            try:
                s = s.encode("utf-8").decode("unicode_escape")
            except Exception:
                pass
    # Normalize (NFC works well across platforms)
    return unicodedata.normalize("NFC", s)

def cell_ref_to_indices(cell_ref):
    column_letters = ''.join(filter(str.isalpha, cell_ref))
    row_number = ''.join(filter(str.isdigit, cell_ref))

    col = sum((ord(char.upper()) - ord('A') + 1) * (26**idx) for idx, char in enumerate(reversed(column_letters))) - 1
    row = int(row_number) - 1
    return col, row

def set_cell_values(new_cell_values: dict[str, str], app_name: str = "Untitled 1", sheet_name: str = "Sheet1"):
    app_name  = _norm_name(app_name)
    sheet_name = _norm_name(sheet_name)

    new_cell_values_idx = {{}}
    for k, v in new_cell_values.items():
        try:
            col, row = cell_ref_to_indices(k)
        except:
            col = row = None

        if col is not None and row is not None:
            new_cell_values_idx[(col, row)] = v

    # Clean up previous TCP connections.
    subprocess.run(
        'echo \"osworld-public-evaluation\" | sudo -S ss --kill --tcp state TIME-WAIT sport = :2002',
        shell=True,
        check=True,
        text=True,
        capture_output=True
    )

    # Dynamically allow soffice to listen on port 2002.
    subprocess.run(
        [
            "soffice",
            "--accept=socket,host=localhost,port=2002;urp;StarOffice.Service"
        ]
    )

    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_context
    )
    context = resolver.resolve(
        f"uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext"
    )
    desktop = context.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", context
    )

    # Collect all LibreOffice-related opened windows.
    documents = []
    for i, component in enumerate(desktop.Components):
        title = component.Title
        doc_type = identify_document_type(component)
        documents.append((i, component, title, doc_type))

    # Find the LibreOffice Calc app and the sheet of interest.
    spreadsheet = [doc for doc in documents if doc[3] == "Calc"]
    selected_spreadsheet = [doc for doc in spreadsheet if doc[2] == app_name]
    if spreadsheet:
        try:
            if selected_spreadsheet:
                spreadsheet = selected_spreadsheet[0][1]
            else:
                spreadsheet = spreadsheet[0][1]

            sheet = spreadsheet.Sheets.getByName(sheet_name)
        except:
            raise ValueError(f"Could not find sheet {{sheet_name}} in {{app_name}}.")

        for (col, row), value in new_cell_values_idx.items():
            cell = sheet.getCellByPosition(col, row)

            # Set the cell value.
            if isinstance(value, (int, float)):
                cell.Value = value
            elif isinstance(value, str):
                if value.startswith("="):
                    cell.Formula = value
                else:
                    cell.String = value
            elif isinstance(value, bool):
                cell.Value = 1 if value else 0
            elif value is None:
                cell.clearContents(0)
            else:
                raise ValueError(f"Unsupported cell value type: {{type(value)}}")

    else:
        raise ValueError(f"Could not find LibreOffice Calc app corresponding to {{app_name}}.")

set_cell_values(new_cell_values={cell_values}, app_name="{app_name}", sheet_name="{sheet_name}")        
"""

def agent_action(func):
    func.is_agent_action = True
    return func

class OSWorldACI:
    def __init__(
        self,
        model: BaseChatModel,
        env,
        platform: str,
        grounding_width: int = 1920,
        grounding_height: int = 1080,
        width: int = 1920,
        height: int = 1080,
    ):
        self.model = model
        self.env = env
        self.platform = platform
        self.grounding_width = grounding_width
        self.grounding_height = grounding_height
        self.width = width
        self.height = height
        self.notes = []
        self.obs = None
        self.last_code_agent_result = None

    def assign_screenshot(self, obs: Dict):
        self.obs = obs

    def set_task_instruction(self, task_instruction: str):
        self.current_task_instruction = task_instruction

    def resize_coordinates(self, coordinates: List[int]) -> List[int]:
        return [
            round(coordinates[0] * self.width / self.grounding_width),
            round(coordinates[1] * self.height / self.grounding_height),
        ]

    def generate_coords(self, ref_expr: str, obs: Dict) -> List[int]:
        prompt = f"Query:{ref_expr}\nOutput only the coordinate of one point in your response.\n"
        
        messages = [
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{obs['screenshot']}"},
                    },
                ]
            )
        ]
        
        response = self.model.invoke(messages).content
        print("RAW GROUNDING MODEL RESPONSE:", response)
        numericals = re.findall(r"\d+", response)
        if len(numericals) >= 2:
            return [int(numericals[0]), int(numericals[1])]
        return [0, 0] # Fallback

    def get_ocr_elements(self, b64_image_data: str) -> Tuple[str, List]:
        image = Image.open(BytesIO(base64.b64decode(b64_image_data)))
        image_data = pytesseract.image_to_data(image, output_type=Output.DICT)

        for i, word in enumerate(image_data["text"]):
            image_data["text"][i] = re.sub(
                r"^[^a-zA-Z\s.,!?;:\-\+]+|[^a-zA-Z\s.,!?;:\-\+]+$", "", word
            )

        ocr_elements = []
        ocr_table = "Text Table:\nWord id\tText\n"
        grouping_map = defaultdict(list)
        ocr_id = 0
        for i in range(len(image_data["text"])):
            block_num = image_data["block_num"][i]
            if image_data["text"][i]:
                grouping_map[block_num].append(image_data["text"][i])
                ocr_table += f"{ocr_id}\t{image_data['text'][i]}\n"
                ocr_elements.append(
                    {
                        "id": ocr_id,
                        "text": image_data["text"][i],
                        "group_num": block_num,
                        "word_num": len(grouping_map[block_num]),
                        "left": image_data["left"][i],
                        "top": image_data["top"][i],
                        "width": image_data["width"][i],
                        "height": image_data["height"][i],
                    }
                )
                ocr_id += 1

        return ocr_table, ocr_elements

    def generate_text_coords(
        self, phrase: str, obs: Dict, alignment: str = ""
    ) -> List[int]:
        ocr_table, ocr_elements = self.get_ocr_elements(obs["screenshot"])

        alignment_prompt = ""
        if alignment == "start":
            alignment_prompt = "**Important**: Output the word id of the FIRST word in the provided phrase.\n"
        elif alignment == "end":
            alignment_prompt = "**Important**: Output the word id of the LAST word in the provided phrase.\n"

        messages = [
            SystemMessage(content=PROCEDURAL_MEMORY.PHRASE_TO_WORD_COORDS_PROMPT),
            HumanMessage(
                content=[
                    {"type": "text", "text": alignment_prompt + "Phrase: " + phrase + "\n" + ocr_table},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{obs['screenshot']}"},
                    },
                ]
            )
        ]

        response = self.model.invoke(messages).content
        print("TEXT SPAN AGENT RESPONSE:", response)
        numericals = re.findall(r"\d+", response)
        if len(numericals) > 0:
            text_id = int(numericals[-1])
        else:
            text_id = 0
        
        if text_id < len(ocr_elements):
            elem = ocr_elements[text_id]
            if alignment == "start":
                coords = [elem["left"], elem["top"] + (elem["height"] // 2)]
            elif alignment == "end":
                coords = [elem["left"] + elem["width"], elem["top"] + (elem["height"] // 2)]
            else:
                coords = [
                    elem["left"] + (elem["width"] // 2),
                    elem["top"] + (elem["height"] // 2),
                ]
            return coords
        return [0, 0]

    @agent_action
    def click(
        self,
        element_description: str,
        num_clicks: int = 1,
        button_type: str = "left",
        hold_keys: List = [],
    ):
        """Click on the element"""
        coords1 = self.generate_coords(element_description, self.obs)
        x, y = self.resize_coordinates(coords1)
        command = "import pyautogui; "

        for k in hold_keys:
            command += f"pyautogui.keyDown({repr(k)}); "
        command += f"""import pyautogui; pyautogui.click({x}, {y}, clicks={num_clicks}, button={repr(button_type)}); """
        for k in hold_keys:
            command += f"pyautogui.keyUp({repr(k)}); "
        return command

    @agent_action
    def switch_applications(self, app_code):
        """Switch to a different application that is already open"""
        if self.platform == "darwin":
            return f"import pyautogui; import time; pyautogui.hotkey('command', 'space', interval=0.5); pyautogui.typewrite({repr(app_code)}); pyautogui.press('enter'); time.sleep(1.0)"
        elif self.platform == "linux":
            return UBUNTU_APP_SETUP.replace("APP_NAME", app_code)
        elif self.platform == "windows":
            return f"import pyautogui; import time; pyautogui.hotkey('win', 'd', interval=0.5); pyautogui.typewrite({repr(app_code)}); pyautogui.press('enter'); time.sleep(1.0)"
        else:
            return "print('Unsupported platform')"

    @agent_action
    def open(self, app_or_filename: str):
        """Open any application or file"""
        if self.platform == "linux":
            return f"import pyautogui; pyautogui.hotkey('win'); time.sleep(0.5); pyautogui.write({repr(app_or_filename)}); time.sleep(1.0); pyautogui.hotkey('enter'); time.sleep(0.5)"
        elif self.platform == "darwin":
            return f"import pyautogui; import time; pyautogui.hotkey('command', 'space', interval=0.5); pyautogui.typewrite({repr(app_or_filename)}); pyautogui.press('enter'); time.sleep(1.0)"
        elif self.platform == "windows":
            return (
                "import pyautogui; import time; "
                "pyautogui.hotkey('win'); time.sleep(0.5); "
                f"pyautogui.write({repr(app_or_filename)}); time.sleep(1.0); "
                "pyautogui.press('enter'); time.sleep(0.5)"
            )
        return "print('Unsupported platform')"

    @agent_action
    def type(
        self,
        element_description: Optional[str] = None,
        text: str = "",
        overwrite: bool = False,
        enter: bool = False,
    ):
        """Type text/unicode into a specific element"""
        command = "import pyautogui; "
        command += (
            "\ntry:\n"
            "    import pyperclip\n"
            "except ImportError:\n"
            "    import subprocess\n"
            "    subprocess.run('echo \"osworld-public-evaluation\" | sudo -S apt-get install -y xclip xsel', shell=True, check=True)\n"
            "    subprocess.check_call([subprocess.sys.executable, '-m', 'pip', 'install', 'pyperclip'])\n"
            "    import pyperclip\n\n"
        )

        if element_description is not None:
            coords1 = self.generate_coords(element_description, self.obs)
            x, y = self.resize_coordinates(coords1)
            command += f"pyautogui.click({x}, {y}); "

        if overwrite:
            command += (
                f"pyautogui.hotkey({repr('command' if self.platform == 'darwin' else 'ctrl')}, 'a'); "
                "pyautogui.press('backspace'); "
            )

        has_unicode = any(ord(char) > 127 for char in text)

        if has_unicode:
            command += f"pyperclip.copy({repr(text)}); "
            command += f"pyautogui.hotkey({repr('command' if self.platform == 'darwin' else 'ctrl')}, 'v'); "
        else:
            command += f"pyautogui.write({repr(text)}); "

        if enter:
            command += "pyautogui.press('enter'); "
        return command

    @agent_action
    def save_to_knowledge(self, text: List[str]):
        """Save facts, elements, texts, etc. to a long-term knowledge bank"""
        self.notes.extend(text)
        return """WAIT"""

    @agent_action
    def drag_and_drop(
        self, starting_description: str, ending_description: str, hold_keys: List = []
    ):
        """Drag from the starting description to the ending description"""
        coords1 = self.generate_coords(starting_description, self.obs)
        coords2 = self.generate_coords(ending_description, self.obs)
        x1, y1 = self.resize_coordinates(coords1)
        x2, y2 = self.resize_coordinates(coords2)

        command = "import pyautogui; "
        command += f"pyautogui.moveTo({x1}, {y1}); "
        for k in hold_keys:
            command += f"pyautogui.keyDown({repr(k)}); "
        command += f"pyautogui.dragTo({x2}, {y2}, duration=1., button='left'); pyautogui.mouseUp(); "
        for k in hold_keys:
            command += f"pyautogui.keyUp({repr(k)}); "
        return command

    @agent_action
    def highlight_text_span(
        self, starting_phrase: str, ending_phrase: str, button: str = "left"
    ):
        """Highlight a text span"""
        coords1 = self.generate_text_coords(
            starting_phrase, self.obs, alignment="start"
        )
        coords2 = self.generate_text_coords(ending_phrase, self.obs, alignment="end")
        x1, y1 = coords1
        x2, y2 = coords2

        command = "import pyautogui; "
        command += f"pyautogui.moveTo({x1}, {y1}); "
        command += f"pyautogui.dragTo({x2}, {y2}, duration=1., button='{button}'); pyautogui.mouseUp(); "
        return command

    @agent_action
    def set_cell_values(
        self, cell_values: Dict[str, Any], app_name: str, sheet_name: str
    ):
        """Use this to set individual cell values in a spreadsheet"""
        return SET_CELL_VALUES_CMD.format(
            cell_values=cell_values, app_name=app_name, sheet_name=sheet_name
        )

    @agent_action
    def call_code_agent(self, task: str = None):
        """Call the code agent to execute code for tasks or subtasks"""
        # Placeholder for code agent integration
        # In a full implementation, this would invoke a sub-graph or another agent
        logger.info("Code agent called (placeholder)")
        return "import time; time.sleep(1.0)"

    @agent_action
    def scroll(self, element_description: str, clicks: int, shift: bool = False):
        """Scroll the element in the specified direction"""
        coords1 = self.generate_coords(element_description, self.obs)
        x, y = self.resize_coordinates(coords1)

        if shift:
            return f"import pyautogui; import time; pyautogui.moveTo({x}, {y}); time.sleep(0.5); pyautogui.hscroll({clicks})"
        else:
            return f"import pyautogui; import time; pyautogui.moveTo({x}, {y}); time.sleep(0.5); pyautogui.vscroll({clicks})"

    @agent_action
    def hotkey(self, keys: List):
        """Press a hotkey combination"""
        keys = [f"'{key}'" for key in keys]
        return f"import pyautogui; pyautogui.hotkey({', '.join(keys)})"

    @agent_action
    def hold_and_press(self, hold_keys: List, press_keys: List):
        """Hold a list of keys and press a list of keys"""
        press_keys_str = "[" + ", ".join([f"'{key}'" for key in press_keys]) + "]"
        command = "import pyautogui; "
        for k in hold_keys:
            command += f"pyautogui.keyDown({repr(k)}); "
        command += f"pyautogui.press({press_keys_str}); "
        for k in hold_keys:
            command += f"pyautogui.keyUp({repr(k)}); "
        return command

    @agent_action
    def wait(self, time: float):
        """Wait for a specified amount of time"""
        return f"""import time; time.sleep({time})"""

    @agent_action
    def done(self):
        """End the current task with a success"""
        return """DONE"""

    @agent_action
    def fail(self):
        """End the current task with a failure"""
        return """FAIL"""
