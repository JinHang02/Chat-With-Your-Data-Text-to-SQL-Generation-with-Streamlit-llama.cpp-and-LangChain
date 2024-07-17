import streamlit as st
import hashlib

from loguru import logger

from style import markdown_style
from prompts import PROMPT_SQL, PROMPT_RESPONSE, PROMPT_REGEN_SQL_V2, MODEL_SETTINGS_MD

def setup_SettingsUI(model_configs: dict, prompt_configs: dict)-> None:
    """Setup for streamlit Model Settings UI"""
    st.title("📜:rainbow[Prompt Template]", anchor = False)
    markdown_style()
    with st.sidebar:
        st.info("This application uses OpenAI API to execute chat completion")
        assistant = change_assistant()
        model_configs = change_model_config(model_configs, assistant)

    st.markdown(MODEL_SETTINGS_MD)
    prompt_configs = change_model_prompt(prompt_configs, assistant)
    update_logs(model_configs, prompt_configs)

def initialize_session_state() -> dict:
    """initialize sessions state for streamlit application"""
    st.session_state.setdefault("temperature_sql", 0)
    st.session_state.setdefault("temperature_response", 0)
    st.session_state.setdefault("model_sql", "sqlcoder-7b-2")
    st.session_state.setdefault("model_response", "Mistral-7B-Instruct-v0.3")
    st.session_state.setdefault("apikey_sql", "")
    st.session_state.setdefault("apikey_response", "")
    st.session_state.setdefault("url_sql", "http://localhost:8080/v1")
    st.session_state.setdefault("url_response", "http://localhost:8080/v1")
    
    st.session_state.setdefault("prompt_sql", PROMPT_SQL)
    st.session_state.setdefault("prompt_regen_sql", PROMPT_REGEN_SQL_V2)
    st.session_state.setdefault("prompt_response", PROMPT_RESPONSE)

    st.session_state.setdefault("isModelConfigChange", False)
    st.session_state.setdefault("isModelPromptChange", False)

    model_configs = {
                    "temperature_sql": st.session_state["temperature_sql"],
                    "temperature_response": st.session_state["temperature_response"],
                    "model_sql": st.session_state["model_sql"], 
                    "model_response": st.session_state["model_response"], 
                    "apikey_sql": st.session_state["apikey_sql"], 
                    "apikey_response": st.session_state["apikey_response"],
                    "url_sql": st.session_state["url_sql"], 
                    "url_response": st.session_state["url_response"]
    }

    prompt_configs = {
        "prompt_sql": st.session_state["prompt_sql"],
        "prompt_regen_sql": st.session_state["prompt_regen_sql"],
        "prompt_response": st.session_state["prompt_response"]
    }

    return model_configs, prompt_configs
    
def change_assistant() -> str:
    """Choose between SQL Assistant or AI Assistant to access settings"""
    assistant= st.sidebar.selectbox(
        "Assistant",
        ("SQL Assistant","AI Assistant")
    )
    if assistant == "AI Assistant":
        icon = "./icons/robot.png"
    else:
        icon = "./icons/sql.png"
    left_co, cent_co,last_co = st.columns(3)
    with cent_co:
        st.image(icon,width = 70)

    return assistant

def change_model_config(model_configs: dict, assistant: str)-> dict:
    """Change model configs such as temperature, model_name, api_key, and base url"""
    if assistant == "AI Assistant":
        name = "response"
    else:
        name = "sql"
    config_keys = [f"temperature_{name}",f"model_{name}",f"apikey_{name}",f"url_{name}"]

    temperature = st.slider(
        "Temperature", 
        min_value = 0.00,
        max_value = 1.00,
        value = float(st.session_state[config_keys[0]]),
        key=f"temperature_input",
        on_change=lambda: (setattr(st.session_state, config_keys[0], st.session_state[f"temperature_input"]),
                            setattr(st.session_state, "isModelConfigChange", True)),
        help = "Temperature controls output randomness: lower for consistency, higher for creativity.")
    model_name = st.text_input("Model Name", 
                               value = st.session_state[config_keys[1]],
                               key="model_name_input",
                                on_change=lambda: (setattr(st.session_state, config_keys[1], st.session_state["model_name_input"]),
                                                    setattr(st.session_state, "isModelConfigChange", True))
                               )
    api_key = st.text_input("API KEY", 
                            type="password",
                            help="Leave blank if using a service emulator", 
                            value = st.session_state[config_keys[2]],
                            key="api_key_input",
                            on_change=lambda: (setattr(st.session_state, config_keys[2], st.session_state["api_key_input"]),
                                                setattr(st.session_state, "isModelConfigChange", True)))
    url = st.text_input("URL (API Request)", 
                         help="Leave blank if not using a proxy or service emulator", 
                         value = st.session_state[config_keys[3]],
                         key="url_input",
                        on_change=lambda: (setattr(st.session_state, config_keys[3], st.session_state["url_input"]),
                                            setattr(st.session_state, "isModelConfigChange", True)))
    config_values = [temperature, model_name, api_key, url]
    model_config = dict(zip(config_keys,config_values))
    model_configs.update(model_config)
    return model_configs

def change_model_prompt(prompt_configs: dict, assistant: str)-> dict:
    """Change model prompts for AI Assistant and SQL Assistant"""
    if assistant == "AI Assistant":
        prompt_response = st.text_area(
            "Prompt Template",
            height = 400,
            value = prompt_configs["prompt_response"],
            key="prompt_response_input",
            on_change=lambda: (setattr(st.session_state, "prompt_response", st.session_state["prompt_response_input"]),
                                setattr(st.session_state, "isModelPromptChange", True)))
        prompt_configs.update({"prompt_response": prompt_response})
    else:
        prompt_sql = st.text_area(
            "Prompt Template",
            height = 400,
            value = prompt_configs["prompt_sql"],
            key="prompt_sql_input",
            on_change=lambda: (setattr(st.session_state, "prompt_sql", st.session_state["prompt_sql_input"]),
                                setattr(st.session_state, "isModelPromptChange", True)))

        prompt_regen_sql = st.text_area(
            "Prompt Template (Regeneration)",
            height = 400,
            help = "Prompt for SQL Assistant to refine or enhance the previously generated SQL query.",
            value = prompt_configs["prompt_regen_sql"],
            key="prompt_regen_sql_input",
            on_change=lambda: (setattr(st.session_state, "prompt_regen_sql", st.session_state["prompt_regen_sql_input"]),
                                setattr(st.session_state, "isModelPromptChange", True)))
    
        prompt_configs.update({"prompt_sql": prompt_sql,
                              "prompt_regen_sql": prompt_regen_sql})
    
    return prompt_configs
    

def update_logs(model_configs: dict, prompt_configs: dict) -> None:
    """Print logs to log file if model configs or model prompts are changed."""
    model_configs_log = model_configs.copy()
    if "apikey_sql" in model_configs_log:
        model_configs_log["apikey_sql"] = hashlib.sha256(model_configs_log["apikey_sql"].encode()).hexdigest()
    if "apikey_response" in model_configs_log:
        model_configs_log["apikey_response"] = hashlib.sha256(model_configs_log["apikey_response"].encode()).hexdigest()
    if st.session_state["isModelConfigChange"]:
        logger.opt(colors=True).info("<blue>Changing model configs...</blue>")
        logger.opt(colors=True).info(f"<yellow>New model configs: {model_configs_log}</yellow>")
        st.session_state["isModelConfigChange"] = False
    elif st.session_state["isModelPromptChange"]:
        logger.opt(colors=True).info("<blue>Changing model prompts...</blue>")
        logger.opt(colors=True).info(f"<yellow>New model prompts: {prompt_configs}</yellow>")
        st.session_state["isModelPromptChange"] = False

def obtain_configs()-> dict:
    """return model configs and prompt configs"""
    model_configs, prompt_configs = initialize_session_state()
    return model_configs, prompt_configs

def main()-> None:
    model_configs, prompt_configs = initialize_session_state()
    setup_SettingsUI(model_configs, prompt_configs)

if __name__ == "__main__":
    main()