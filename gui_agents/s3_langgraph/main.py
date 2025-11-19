import argparse
import os
import io
import base64
import pyautogui
import platform
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from gui_agents.s3_langgraph.utils import OSWorldACI
from gui_agents.s3_langgraph.graph import create_graph

# Load environment variables
load_dotenv()

def get_model(provider: str, model_name: str, temperature: float = 0.0):
    if provider == "openai":
        return ChatOpenAI(model=model_name, temperature=temperature)
    elif provider == "anthropic":
        return ChatAnthropic(model=model_name, temperature=temperature)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

def main():
    parser = argparse.ArgumentParser(description="Run AgentS3 with LangGraph.")
    parser.add_argument("--provider", type=str, default="openai", help="Model provider (openai, anthropic)")
    parser.add_argument("--model", type=str, default="gpt-4o", help="Model name")
    parser.add_argument("--grounding_provider", type=str, default="openai", help="Grounding model provider")
    parser.add_argument("--grounding_model", type=str, default="gpt-4o", help="Grounding model name")
    
    args = parser.parse_args()
    
    # Initialize models
    worker_model = get_model(args.provider, args.model)
    grounding_model = get_model(args.grounding_provider, args.grounding_model)
    
    # Initialize environment (LocalEnv placeholder if needed, but we use direct pyautogui)
    # OSWorldACI expects 'env' but we can pass None if we don't use the complex env wrapper
    # The original code passed 'local_env' or None.
    
    screen_width, screen_height = pyautogui.size()
    
    grounding_agent = OSWorldACI(
        model=grounding_model,
        env=None,
        platform=platform.system().lower(),
        width=screen_width,
        height=screen_height,
        grounding_width=screen_width, # Assuming no scaling for now or same as screen
        grounding_height=screen_height
    )
    
    # Create graph
    app = create_graph(worker_model, grounding_agent)
    
    print("AgentS3 (LangGraph) initialized.")
    
    while True:
        query = input("\nQuery: ")
        if query.lower() in ["exit", "quit"]:
            break
            
        print("Capturing screenshot...")
        screenshot_img = pyautogui.screenshot()
        buffered = io.BytesIO()
        screenshot_img.save(buffered, format="PNG")
        screenshot_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        initial_state = {
            "messages": [],
            "screenshot": screenshot_b64,
            "instruction": query,
            "notes": [],
            "scratchpad": {},
            "loop_step": 0
        }
        
        print("Running agent...")
        for event in app.stream(initial_state):
            for key, value in event.items():
                print(f"\n--- Node: {key} ---")
                if "messages" in value:
                    print(value["messages"][-1].content)
                    
        print("\nTask finished.")

if __name__ == "__main__":
    main()
