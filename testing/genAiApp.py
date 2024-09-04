import streamlit as st
import json

import vertexai
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel
from google.cloud import discoveryengine_v1 as discoveryengine
from google.protobuf.json_format import MessageToDict


project_id = "genai-metalwork-dev-mscdirect"
vais_location = "us"
engine_id = "ata-mwgenaiassist"

client_options = (
        ClientOptions(api_endpoint=f"{vais_location}-discoveryengine.googleapis.com")
        if vais_location != "global"
        else None
    )

client = discoveryengine.SearchServiceClient(client_options=client_options)
serving_config = f"projects/{project_id}/locations/{vais_location}/collections/default_collection/engines/{engine_id}/servingConfigs/default_config"

content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
    snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
        return_snippet=True
    ),
    summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
        summary_result_count=5,
        include_citations=True,
        ignore_adversarial_query=True,
        ignore_non_summary_seeking_query=True,
        # model_prompt_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec.ModelPromptSpec(
        #     preamble="YOUR_CUSTOM_PROMPT"
        # ),
        model_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec.ModelSpec(
            version="stable",
        ),
    ),
)

# Logic for collecting parameters and chat functions

def start_chat_session():
  vertexai.init(project=project_id, location="us-east4")

  system_instruction='''
  You are a friendly and helpful conversational chatbot. You can answer a wide range of questions.

  You should politely ask the user for the following information, one question at a time, until you have all the details. The user could provide all the details in a single line:

  * **Wire Type:** What is the type of the wire?
  * **Wire Size:** What size wire?

  *Rule*
  If field is not fulfilled value should be an empty string.

  Once you have gathered all the necessary information, let the user know you have everything you need. You don't need to make the prediction yourself, just gather the data.
  { "response": "<your response>",
    "fulfilled": <true or false (true only if all Fields_required_for_point_2 are filled)>,
    "wire_type" :  <a string or empty if not fulfilled>,
    "wire_size" :  <a number or empty if not fulfilled (double)>,
  **Output your responses in this JSON format:**
  '''

  chatbot_generation_config = {
      "max_output_tokens": 8192,
      "temperature": 1,
      "top_p": 0.95,
      "response_mime_type": "application/json",
  }

  chat_model = GenerativeModel(
      "gemini-1.5-flash-001",
      system_instruction=system_instruction,
      generation_config=chatbot_generation_config,
  )
  chat = chat_model.start_chat()
  return chat

# Vertex Search Logic

def execute_vaiss_query(input): # 16 AWG, UF
  user_message = f"provide details for a wire with the following specifications: Size: {input['wire_size']}, Type: {input['wire_type']}"
  request = discoveryengine.SearchRequest(
      serving_config=serving_config,
      query=user_message,
      page_size=10,
      content_search_spec=content_search_spec,
      query_expansion_spec=discoveryengine.SearchRequest.QueryExpansionSpec(
          condition=discoveryengine.SearchRequest.QueryExpansionSpec.Condition.AUTO,
      ),
      spell_correction_spec=discoveryengine.SearchRequest.SpellCorrectionSpec(
          mode=discoveryengine.SearchRequest.SpellCorrectionSpec.Mode.AUTO
      ),
  )
  response = client.search(request)
  print(response)

  # response_text = f"Summary: {response.summary.summary_text}\nCitations: {response.summary.references}"
  return response.summary.summary_with_metadata

# Main app logic

chat = start_chat_session()

# Streamlit Logic

if "chat" not in st.session_state:
  st.session_state.chat = start_chat_session()
else:
  chat = st.session_state.chat

if "history" not in st.session_state:
  st.session_state.history = st.session_state.chat.history

st.title("AI Chatbot")


for message in st.session_state.history:
    with st.chat_message(message.role):
        st.markdown(message.parts[0].text)

if prompt := st.chat_input("How can I help you today?"):

    with st.chat_message("user"):
        st.markdown(prompt)

    response = chat.send_message(prompt)

    text_output = json.loads(response.candidates[0].content.parts[0].text)

    with st.chat_message("assistant"):
        st.markdown(response.candidates[0].content.parts[0].text)
        # st.markdown(response.candidates[0].content.parts[0].text)

    if text_output["fulfilled"] == True:
       st.markdown(execute_vaiss_query(text_output))
