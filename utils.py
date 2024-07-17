import datetime
import sys
import streamlit as st

from loguru import logger
from langchain_openai import OpenAI
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.callbacks.base import BaseCallbackHandler

from langchain_utils import SQLDatabaseChain #custom modified langchain
from prompts import STREAM_MSG, STREAM_MSG_SCHEMA_MODE
sys.path.append('/home/user/.local/lib/python3.10/site-packages') #TODO: remove soon

def createlog(isSetup: bool) -> None:
    """Create logs for each session"""
    now = datetime.datetime.now()
    now = str(now)[:-7].replace(" ",".")
    log_level = "DEBUG"
    log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS zz}</green> | <level>{level: <8}</level> | <yellow>Line {line: >4} ({file}):</yellow> <b>{message}</b>"
    if isSetup:
        # ensure that setup log is created at first time setup only
        logger.add(f"./logs/{now}.log", level=log_level, format=log_format, colorize=False, backtrace=True, diagnose=True)
        logger.info(f"Creating new log file on {now}")

class StreamHandler(BaseCallbackHandler): 
    """
    To stream generated token in main application and print as 'assistant' message or 'sql' message
    """
    def __init__(self, initial_text=""):
        self.initial_text = initial_text
        self.text = initial_text

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """stream tokens when producing new token"""
        self.text += token
        st.markdown(self.text)
    
    def on_llm_end(self, response, **kwargs) -> None:
        """print the whole message when stop producing new token"""
        if self.initial_text != "":
            st.markdown(f"{self.text}  \n ```")

class SQL2TextPipeline():
    """
    A SQL to Text Pipeline that contains the setup of two LLMs, which are sqlcoder-7b-2 and Mistral-7B-Instruct-v0.3.
    sqlcoder-7b02 used is a quantized 8-bit precision gguf model to generate Text-to-SQL conversion.
    It is a finetuned model of CodeLlama-7B to be specialised at Natural Language to SQL generation.
    Mistral-7B-Instruct-v0.3 used is a quantized 8-bit precision gguf model to generate human response based on sql results.
    Both of the models are served by llama.cpp server and it has the same OpenAI API policy, thus it serves as a good
    alternative as OpenAI-compatible server.
    The pipeline also contains setup of SQLite database. In the end, the pipeline will return two langchains to the main 
    application to do inference by invoking the chains.
    
    Models used in this application:
    Model_sql     : https://huggingface.co/MaziyarPanahi/sqlcoder-7b-2-GGUF
    Model_response: https://huggingface.co/MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF

    """
    def __init__(self):
        self.stream_handler_response = StreamHandler()
        self.stream_handler_sql = StreamHandler(initial_text=STREAM_MSG)
        self.stream_handler_sql_schema_mode = StreamHandler(initial_text=STREAM_MSG_SCHEMA_MODE)

    @classmethod
    def change_query(cls, sql_dict, db)-> dict:
        """Change query if db is sqlite3"""
        if db.dialect != "sqlite":
            return sql_dict
        if "ilike" in sql_dict['result'].lower():
            sql_dict['result'] = sql_dict['result'].replace("ilike","like")
            sql_dict['result'] = sql_dict['result'].replace("ILIKE","LIKE")
        return sql_dict
    
    @classmethod
    def check_dml_ops(cls, sql_query: str)-> bool: 
        """validate DML operations produced by LLM so that it doesnt perform write operations"""
        dml_ops_list = ["CREATE","INSERT", "UPDATE", "DELETE", "DROP","ALTER","TRUNCATE","MERGE","UPSERT"]
        if any(dml in sql_query for dml in dml_ops_list):
            logger.warning(f"Query contains write operations: {sql_query}")
            return False
        return True
    
    @classmethod
    def test_query(cls, db, query: str)-> list:
        """test whether sql query is runnable"""
        try:
            db.run(query)
        except:
            raise Exception
    
    def _get_db(self):
        """to obtain created object "db" """
        return self.db
    
    def _get_response_prompt(self)-> str:
        """to obtain created object of prompts for human-readable response generation"""
        return self.prompt_response
    
    def setup(self, isSetup: bool, configs: dict, model_configs: dict, prompt_configs: dict)-> None:
        """Function to setup prompts, llm, and db connection"""
        createlog(isSetup) 
        self._init_prompt(prompt_configs)
        self._init_llm(model_configs)
        self._init_db(configs)

    def _init_llm(self, model_configs: dict)-> None:
        """initialise llm by connecting to openai server"""
        try:
            self.llm_sql = OpenAI(
                    model= model_configs['model_sql'],
                    api_key= model_configs['apikey_sql'] if model_configs['apikey_sql'] != '' else "empty",
                    base_url= model_configs['url_sql'] if model_configs['url_sql'] != '' else None,
                    temperature= model_configs['temperature_sql'],
                    streaming = True,
                    callbacks = [self.stream_handler_sql]
                    )
            
            self.llm_sql_schema_mode = OpenAI(
                    model= model_configs['model_sql'],
                    api_key= model_configs['apikey_sql'] if model_configs['apikey_sql'] != '' else "empty",
                    base_url= model_configs['url_sql'] if model_configs['url_sql'] != '' else None,
                    temperature= model_configs['temperature_sql'],
                    streaming = True,
                    callbacks = [self.stream_handler_sql_schema_mode]
                    )
            
            self.llm_response = OpenAI(
                    model= model_configs['model_response'],
                    api_key= model_configs['apikey_response'] if model_configs['apikey_response'] != '' else "empty",
                    base_url= model_configs['url_response'] if model_configs['url_response'] != '' else None,
                    temperature = model_configs['temperature_response'],
                    streaming = True,
                    callbacks = [self.stream_handler_response]
                    )
        except:
            raise Exception("Model name, API key, or URL address is incorrect/unavailable.")
        
    def _init_prompt(self, prompt_configs: dict)-> None:
        """initialise prompts by obtaining from frontend"""
        prompt_validity, missing_keys, prompt = self._check_prompt_keys(prompt_configs)
        if prompt_validity:
            self.prompt_sql = prompt_configs['prompt_sql']
            self.prompt_response = prompt_configs['prompt_response']
            self.prompt_regen_sql = prompt_configs['prompt_regen_sql']
        else:
            missing_keys = ', '.join(missing_keys) if isinstance(missing_keys, list) else missing_keys
            raise Exception(f"Missing key {missing_keys} in {prompt}")
    
    def _check_prompt_keys(self, prompt_configs: dict):
        """check whether prompts contain keys required for inference."""
        keys_list = [
            ["{input}","{table_info}","{history}"],
            ["{history}","{question}","{query}","{results}"],
            ["{input}","{table_info}","{wrong_sql_query}"]
        ]
        prompt_list = ["prompt_sql","prompt_response","prompt_regen_sql"]
        display_name = ["prompt template of SQL Assistant",
                        "prompt template of AI Assistant",
                        "prompt template(Regeneration) of SQL Assistant"]
        for i,keys in enumerate(keys_list):
            missing_keys = [key for key in keys if key not in prompt_configs[prompt_list[i]]]
            if missing_keys != []:
                return False, missing_keys, display_name[i]
        return True, None , None

    def _init_db(self, configs)-> None:
        """Connect to database to get access to it"""
        try:
            if not configs['isdbSchemaMode']:
                if configs['db_type'] == 'SQLite':
                    address = f"sqlite:///sqlite/{configs['db_name_sqlite']}"
                elif configs['db_type'] == 'PostgreSQL':
                    address = f"postgresql+psycopg2://{configs['username']}:{configs['password']}@{configs['hostname']}:{configs['port']}/{configs['db_name_postgres']}"
                #exclude all sample rows because sqlcoder-7b-2 is finetuned purely using database schema without sample rows.
                self.db = SQLDatabase.from_uri(address, sample_rows_in_table_info = 0)
            else:
                self.db = None 
        except Exception as error:
            raise Exception("Database could not be found. Please ensure database details are correct.")

        # logger.debug(f"Dialect: {self.db.dialect}")
        # logger.debug(f"Table_Names: {self.db.get_usable_table_names()}")

    def create_sql_chain(self, mode: str, task: str):
        """create Langchain object of sql_chain for invoke in main application to create sql query based on user input"""
        try:
            if task == "gen":
                formatted_prompt_sql = self.prompt_sql
            elif task == "regen":
                formatted_prompt_sql = self.prompt_regen_sql
            # logger.debug(f"Prompt_SQL: {formatted_prompt_sql}") #dev purpose
            prompt = PromptTemplate.from_template(template = formatted_prompt_sql)
            if mode == "standard":
                sql_chain = SQLDatabaseChain.from_llm(
                    self.llm_sql, self.db, prompt=prompt, return_sql=True, verbose=False, use_query_checker = False
                )
            elif mode == "schema_mode":
                output_parser = StrOutputParser()
                sql_chain = prompt | self.llm_sql_schema_mode | output_parser
            return sql_chain, prompt
        except Exception as error:
            logger.error(str(error))

    def create_response_chain(self):
        """create Langchain object of response_chain for invoke in main application to create human-readable response based on sql query"""
        try:
            output_parser = StrOutputParser()
            response_chain = self.llm_response | output_parser
            return response_chain
        except Exception as error:
            logger.error(str(error))