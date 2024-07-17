import streamlit as st
import hashlib
from loguru import logger

from style import markdown_style
from prompts import SCHEMA_PROMPT, SCHEMA_MODE_MD

def setup_ChatUI_sidebar() -> dict:
    """setup for streamlit Chat UI sidebar"""
    st.title("🤖 Chat With Your :green[Data]", anchor = False)
    markdown_style()
    initialize_session_state()
    with st.sidebar:
        configs = change_mode()
        if configs["isdbSchemaMode"]:
            configs = db_schema_mode(configs)
        else:
            configs = standard_mode(configs)
    if configs["isdbSchemaMode"]:
        st.markdown(SCHEMA_MODE_MD)
    update_logs(configs)

    return configs

def initialize_session_state() -> None:
    """initialize sessions state for streamlit application"""
    config_keys = ["db_type", "db_name_postgres", "username", "password", "hostname", "port"]
    for k in config_keys:
        st.session_state.setdefault(k,"")
    st.session_state.setdefault("db_name_sqlite", "Chinook.db") 
    st.session_state.setdefault("db_schema", SCHEMA_PROMPT)
    st.session_state.setdefault("isdbSchemaMode", False)
    st.session_state.setdefault("isConfigChange", False)
    
def change_mode() -> dict:
    """Choose mode between standard mode and schema mode"""
    isdbSchemaMode = st.toggle("Database Schema Mode", help="Toggle ON to activate database schema mode")
    configs = {"isdbSchemaMode": isdbSchemaMode}
    if isdbSchemaMode != st.session_state['isdbSchemaMode']:
        st.session_state["isConfigChange"] = True
        logger.opt(ansi=True).info("<blue>Changing mode...</blue>")
    st.session_state["isdbSchemaMode"] = isdbSchemaMode
    return configs

def standard_mode(configs: dict) -> dict:
    """Choose between sqlite or postgresql to continue executing actions for standard mode"""
    select_db= st.sidebar.selectbox(
        "Database Type",
        ("SQLite","PostgreSQL")
    )
    if select_db == "PostgreSQL":
        db_type = "PostgreSQL"
        db_name_postgres = st.text_input("Database Filename", 
                                         value=st.session_state["db_name_postgres"],
                                         key="db_name_postgres_input",
                                         on_change=lambda: (setattr(st.session_state, 
                                                                    "db_name_postgres", 
                                                                    st.session_state["db_name_postgres_input"]),
                                                            setattr(st.session_state, "isConfigChange", True)))
        username = st.text_input("Database username",
                                 value=st.session_state["username"] ,
                                 key="username_input",
                                on_change=lambda: (setattr(st.session_state, "username", st.session_state["username_input"]),
                                                   setattr(st.session_state, "isConfigChange", True)))
        password = st.text_input("Database password",
                                 value=st.session_state["password"],
                                 type="password",
                                 key="password_input",
                                on_change=lambda: (setattr(st.session_state, "password", st.session_state["password_input"]),
                                                   setattr(st.session_state, "isConfigChange", True)))
        hostname = st.text_input("Hostname / IP address",
                                 value=st.session_state["hostname"],
                                key="hostname_input",
                                on_change=lambda: (setattr(st.session_state, "hostname", st.session_state["hostname_input"]),
                                                   setattr(st.session_state, "isConfigChange", True)))
        port = st.text_input("Port Number",
                             value = st.session_state["port"],
                             key="port_input",
                            on_change=lambda: (setattr(st.session_state, "port", st.session_state["port_input"]),
                                               setattr(st.session_state, "isConfigChange", True)))
        config_values = [db_type, db_name_postgres, username, password, hostname, port]
        new_keys = ["db_type", "db_name_postgres", "username", "password", "hostname", "port"]
        db_config = dict(zip(new_keys, config_values))
    else:
        db_type = "SQLite"
        db_name_sqlite = st.text_input("Database Filename", 
                                       value = st.session_state["db_name_sqlite"],
                                       key="db_name_sqlite_input",
                                        on_change=lambda: (setattr(st.session_state, 
                                                                   "db_name_sqlite",
                                                                    st.session_state["db_name_sqlite_input"]),
                                                           setattr(st.session_state, "isConfigChange", True)))
        config_values = [db_type, db_name_sqlite]
        new_keys = ["db_type", "db_name_sqlite"]
        db_config = dict(zip(new_keys, config_values))
        if st.session_state['isConfigChange']:
            st.toast("Please ensure database is in 'sqlite' directory.", icon="🚨")
    configs.update(db_config)
    return configs

def db_schema_mode(configs) -> dict:
    """allow user to run schema mode with their own db schema"""
    db_schema = st.text_area(
        "Database Schema",
        height = 600,
        value = st.session_state["db_schema"],
        key="db_schema_input",
        on_change=lambda:(setattr(st.session_state, "db_schema", st.session_state["db_schema_input"]),
                        setattr(st.session_state, "isConfigChange", True))
        )
    configs.update({"db_schema": db_schema})
    return configs
    
def update_logs(configs) -> None:
    """Print logs to log file if configs are changed."""
    configs_log = configs.copy()
    if 'password' in configs_log:
        password = configs_log['password']
        configs_log['password'] = hashlib.sha256(password.encode()).hexdigest()
    if st.session_state["isConfigChange"]:
        logger.opt(colors=True).info("<blue>Changing configs...</blue>")
        logger.opt(colors=True).info(f"<yellow>New configs: {configs_log}</yellow>")
        st.session_state["isConfigChange"] = False
