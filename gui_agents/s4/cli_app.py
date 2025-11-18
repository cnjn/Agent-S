import argparse
import datetime
import logging
import os
import platform
import signal
import sys
import time

import pyautogui

from gui_agents.s3.agents.grounding import OSWorldACI
from gui_agents.s3.utils.local_env import LocalEnv
from gui_agents.s4.agent import AgentS4

current_platform = platform.system().lower()
paused = False


def get_char():
    try:
        if platform.system() in ["Darwin", "Linux"]:
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch
        else:
            import msvcrt

            return msvcrt.getch().decode("utf-8", errors="ignore")
    except Exception:
        return input()


def signal_handler(signum, frame):
    global paused
    if not paused:
        print("\n\n🔸 Agent-S4 Workflow Paused 🔸")
        print("=" * 50)
        print("Options:")
        print("  • Press Ctrl+C again to quit")
        print("  • Press Esc to resume workflow")
        print("=" * 50)
        paused = True
        while paused:
            try:
                print("\n[PAUSED] Waiting for input... ", end="", flush=True)
                char = get_char()
                if ord(char) == 3:
                    print("\n\n🛑 Exiting Agent-S4...")
                    sys.exit(0)
                elif ord(char) == 27:
                    print("\n\n▶️  Resuming Agent-S4 workflow...")
                    paused = False
                    break
                else:
                    print(f"\n   Unknown command: '{char}' (ord: {ord(char)})")
            except KeyboardInterrupt:
                print("\n\n🛑 Exiting Agent-S4...")
                sys.exit(0)
    else:
        print("\n\n🛑 Exiting Agent-S4...")
        sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)

logger = logging.getLogger("desktopenv.agent.s4")
logger.setLevel(logging.DEBUG)

datetime_str = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

file_handler = logging.FileHandler(
    os.path.join(log_dir, f"s4-normal-{datetime_str}.log"), encoding="utf-8"
)
debug_handler = logging.FileHandler(
    os.path.join(log_dir, f"s4-debug-{datetime_str}.log"), encoding="utf-8"
)
stdout_handler = logging.StreamHandler(sys.stdout)

for handler in (file_handler, debug_handler, stdout_handler):
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s \x1b[32m%(module)s/%(lineno)d-%(processName)s\x1b[1;33m] \x1b[0m%(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def show_permission_dialog(code: str, action_description: str):
    if platform.system() == "Darwin":
        result = os.system(
            f'osascript -e \'display dialog "Execute this action?\\n\\n{code} which will try to {action_description}" with title "Agent-S4 Permission" buttons {{"Cancel", "OK"}} default button "OK" cancel button "Cancel"\''
        )
        return result == 0
    elif platform.system() == "Linux":
        result = os.system(
            f'zenity --question --title="Agent-S4 Permission" --text="Execute this action?\\n\\n{code}" --width=400 --height=200'
        )
        return result == 0
    return True


def scale_screen_dimensions(width: int, height: int, max_dim_size: int):
    scale_factor = min(max_dim_size / width, max_dim_size / height, 1)
    safe_width = int(width * scale_factor)
    safe_height = int(height * scale_factor)
    return safe_width, safe_height


def execute_agent_code(payload: dict):
    global paused
    code = payload.get("code", "")
    plan = payload.get("plan") or ""
    turn = payload.get("turn")

    print("\n" + "=" * 80)
    print(f"🧠 LangGraph planned Step {turn}:")
    print(plan)
    print("-" * 80)
    print(code)
    print("=" * 80)

    normalized = code.strip().upper()
    if normalized in {"DONE", "FAIL"}:
        print(f"⚡ Agent returned terminal signal: {normalized}")
        return {"status": "ok", "done": True, "notes": [normalized]}

    if not show_permission_dialog(code, "interact with your desktop"):
        print("⚠️  User rejected execution.")
        return {
            "status": "fail",
            "fail_reason": "User rejected execution",
            "notes": ["User rejected execution"],
        }

    while paused:
        time.sleep(0.1)

    try:
        exec(code, {}, {})
        return {
            "status": "ok",
            "observation": "Code executed successfully.",
            "notes": [f"Executed at {datetime.datetime.now().isoformat()}"],
        }
    except Exception as exc:
        logger.exception("执行代码失败: %s", exc)
        return {
            "status": "fail",
            "fail_reason": str(exc),
            "observation": repr(exc),
        }


def parse_args():
    parser = argparse.ArgumentParser(description="Run AgentS4 on LangGraph.")
    parser.add_argument("--provider", type=str, default="openai")
    parser.add_argument("--model", type=str, default="gpt-4o")
    parser.add_argument("--model_url", type=str, default="")
    parser.add_argument("--model_api_key", type=str, default="")
    parser.add_argument("--model_temperature", type=float, default=None)
    parser.add_argument("--ground_provider", type=str, required=True)
    parser.add_argument("--ground_url", type=str, required=True)
    parser.add_argument("--ground_api_key", type=str, default="")
    parser.add_argument("--ground_model", type=str, required=True)
    parser.add_argument("--grounding_width", type=int, required=True)
    parser.add_argument("--grounding_height", type=int, required=True)
    parser.add_argument("--max_trajectory_length", type=int, default=12)
    parser.add_argument("--enable_local_env", action="store_true", default=False)
    return parser.parse_args()


def main():
    args = parse_args()

    screen_width, screen_height = pyautogui.size()
    scaled_width, scaled_height = scale_screen_dimensions(screen_width, screen_height, 2400)

    engine_params = {
        "engine_type": args.provider,
        "model": args.model,
        "base_url": args.model_url,
        "api_key": args.model_api_key,
        "temperature": getattr(args, "model_temperature", None),
    }

    ground_params = {
        "engine_type": args.ground_provider,
        "model": args.ground_model,
        "base_url": args.ground_url,
        "api_key": args.ground_api_key,
        "grounding_width": args.grounding_width,
        "grounding_height": args.grounding_height,
    }

    local_env = LocalEnv() if args.enable_local_env else None

    grounding_agent = OSWorldACI(
        env=local_env,
        platform=current_platform,
        engine_params_for_generation=engine_params,
        engine_params_for_grounding=ground_params,
        width=screen_width,
        height=screen_height,
    )

    agent = AgentS4(
        engine_params,
        grounding_agent,
        platform=current_platform,
        max_turns=args.max_trajectory_length,
        scaled_width=scaled_width,
        scaled_height=scaled_height,
    )

    while True:
        try:
            query = input("Query: ")
        except EOFError:
            break

        if not query.strip():
            continue

        agent.reset()
        result = agent.start(query)

        while "__interrupt__" in result:
            interrupt_payload = result["__interrupt__"][0].value
            resume_payload = execute_agent_code(interrupt_payload)
            result = agent.resume(resume_payload)

        if result.get("fail_reason"):
            print(f"❌ Task failed: {result['fail_reason']}")
        else:
            print("✅ Task complete.")

        cont = input("Continue? (y/n): ")
        if cont.lower() != "y":
            break


if __name__ == "__main__":
    main()

