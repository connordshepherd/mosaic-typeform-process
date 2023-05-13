from flask import Flask, request, jsonify, send_from_directory
import os
import json
import requests
import re
from langchain import PromptTemplate
from langchain.llms import OpenAIChat
openaichat = OpenAIChat(model_name="gpt-3.5-turbo")
BASEPLATE_API_KEY = os.environ['BASEPLATE_API_KEY']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']

# FUNCTIONS AND MORE DEFINITIONS

def query_vector_database(value):
    url = "https://app.baseplate.ai/api/datasets/81699ec2-d00f-4188-932d-00a9e89d14f6/search"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BASEPLATE_API_KEY}"
    }

    data = {
        "query": value,
        "top_k": 15,
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response.json()

def query_provider_database(value, care_type, zip_codes):
    url = "https://app.baseplate.ai/api/datasets/a7704a6a-3030-4594-9e4a-27e49cf8b9d4/search"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BASEPLATE_API_KEY}"
    }

    data = {
        "query": value,
        "top_k": 20,
        "filter": {"zip": {"$in": zip_codes}, "type":care_type},
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response.json()

def generate_zip_range(user_zip, range_size=5):
    user_zip_int = int(user_zip)
    return [str(user_zip_int - i) for i in range(range_size, 0, -1)] + [str(user_zip_int + i) for i in range(range_size + 1)]

def get_truncated_results(results, max_length=100):
    truncated_results = []
    for result in results:
        truncated_text = result['data']['text'][:max_length] + '...' if len(result['data']['text']) > max_length else result['data']['text']
        truncated_result = {
            "truncated_text": truncated_text,
            "title": result['data']['title'],
            "site_url": result['metadata']['site_url'],
            "desc": result['data']['desc']
        }
        truncated_results.append(truncated_result)
    return truncated_results

def get_truncated_provider_results(results, max_length=100):
    truncated_results = []
    for result in results:
        truncated_text = result['data']['text'][:max_length] + '...' if len(result['data']['text']) > max_length else result['data']['text']
        truncated_result = {
            "truncated_text": truncated_text,
            "name": result['data']['name'],
            "rating": result['data']['rating'],
            "site": result['data']['site'],
            "loc": result['data']['loc']
        }
        truncated_results.append(truncated_result)
    return truncated_results

def extract_care_data(survey_data):
    def dict_to_string(data):
        formatted_string = ""
        for key, value in data.items():
            formatted_string += key + ": " + str(value) + "\n"
        return formatted_string

    if isinstance(survey_data, dict):
        survey_data = dict_to_string(survey_data)

    print("Survey data:")
    print(survey_data)

    care_type = ""
    user_zip = ""
    first_name = ""

    name_search = re.search(r"What's your first and last name\? (.*?)  ", survey_data)
    if name_search:
        full_name = name_search.group(1)
        first_name = full_name.split(' ')[0]

    care_preferences_search = re.search(r"What are your/your loved one’s care preferences\? (.*?)  ", survey_data)
    if care_preferences_search:
        care_preferences = care_preferences_search.group(1)
        if "Residential Care" in care_preferences:
            care_type = "Memory Care"
        elif "Adult Day Care" in care_preferences:
            care_type = "Adult Care"
        else:
            care_type = "Home Care"

    user_zip_search = re.search(r"Finally, what is your zip code\? (\d+)", survey_data)
    if user_zip_search:
        user_zip = user_zip_search.group(1)

    return first_name, care_type, user_zip

#APP STARTS

app = Flask(__name__, static_folder='static')

@app.route('/process-typeform', methods=['POST'])
def process_typeform():

    typeform_data = request.json
    first_name, care_type, user_zip = extract_care_data(typeform_data)
    print("Care Type:", care_type)
    print("User Zip:", user_zip)
    print("First Name:", first_name)

    template = """Subject: Your Mosaic Care Plan

    Dear {first_name},

    I wanted to personally reach out and thank you for entrusting Mosaic Care Solutions to help you find solutions for your loved one's care needs. We understand that navigating care services for older adults can be overwhelming, and we're here to help ease your burden.

    Once you have the right care in place, you will find the journey of caregiving to be rewarding and fulfilling. Our job is to help you get there as quickly and easily as possible. Our curated set of options will enable you to choose the right care solution for your loved one’s needs and preferences.

    Please find below your curated set of care options based on the questionnaire you completed. We provide tailored resources based on what we think will be most useful for you. We recommend that you also leverage the knowledge library, community support group and virtual assistant included in your membership. Together, they provide the mosaic of support and resources to help you and your loved one.

    Thank you for trusting Mosaic Care Solutions.

    Sincerely,
    Mosaic Care Team
    """

    prompt = PromptTemplate(template=template, input_variables=["first_name"])
    formatted_prompt = prompt.format(first_name=first_name)
    email_opening = formatted_prompt
    print(email_opening)

    template = """Mosaic Care is a company that recommends memory care providers to people whose parents have been diagnosed with Alzheimer's or other memory problems (these are Mosaic's customers). I have a vector database of the memory care providers.
    
    Mosaic's customers, when they sign up, fill out a survey that gives information for what exactly they are looking for. The output of one survey is below. What I would like you to do is read the survey and create one sentence describing the kind of care provider they are probably looking for.
    
    DESIRED FORMAT: "A provider offering (care preferences) for patients diagnosed with (diagnosis) experiencing symptoms like (symptoms).
    
    EXAMPLE: "A provider offering Support Groups and Scheduled Activities for patients diagnosed with Alzheimer's disease experiencing symptoms like Aphasia and Dementia."
    
  ------
  
  SURVEY RESULTS
  
  {survey}
    """
    prompt = PromptTemplate(template=template, input_variables=["survey"])
    formatted_prompt = prompt.format(survey=typeform_data)
    provider_query = openaichat(formatted_prompt)

    template = """Mosaic Care is a company that recommends research to people whose parents have been diagnosed with Alzheimer's or other memory problems (these are Mosaic's customers). I have a vector database of articles that might be relevant to them.

Mosaic's customers, when they sign up, fill out a survey that gives information for what exactly they are looking for. The output of one survey is below. What I would like you to do is read the survey and create one sentence describing the kind of research they should do.

DESIRED FORMAT: "Articles about people with a diagnosis of (diagnosis) who are experiencing symptoms like (symptoms).

Here are a few examples of the format:

EXAMPLE A: "Articles about people with a diagnosis of Alzheimer's disease who are experiencing symptoms like Aphasia and Dementia."
EXAMPLE B: "Articles about people with a diagnosis of Vascular dementia who are experiencing symptoms like difficulty communicating or finding words."
EXAMPLE C: "Articles about people with a diagnosis of Lewy body dementia who are experiencing symptoms like inappropriate behavior."

------

SURVEY RESULTS

{survey}
"""

    prompt = PromptTemplate(template=template, input_variables=["survey"])
    formatted_prompt = prompt.format(survey=typeform_data)
    research_query = openaichat(formatted_prompt)

    # Save the JSON result as a variable (for category "stay")
    research_vector_query_result = query_vector_database(research_query)

    # Get the truncated JSON object
    truncated_research_vector_query_result = get_truncated_results(research_vector_query_result['results'], max_length=500)

    # Print the JSON object
    print(truncated_research_vector_query_result)

    template = """Mosaic Care is a company that recommends research to people whose parents have experienced symptoms of Alzheimer's or other memory problems (these are Mosaic's customers). I have a vector database of articles that might be relevant to them.

    A customer is looking for {research_query}.

    Below please find chunks of text for the articles most relevant to their search. I'd like you to do the following:
    1) Look at the metadata for "title" and "site_url" to see if there are any duplicates. If there aren't any, you don't need to say so in your response.
    2) Prepare a short reading list including the title of each article, the site_url for each one, and one sentence you compose that tells the customer why they should read the article.

    Please ONLY recommend articles from the results below.

    One important thing - If the customer is looking for articles about people with a diagnosis, they don't want to read any articles with "signs of" or "early signs" their diagnosis. So if an article has those or similar phrases in the title, don't include it in the list.

    Make sure to include the link to the article in the reading list - it's listed as 'site_url' in the metadata.

    ------

    DATABASE RESULTS

    {context}
    """
    
    prompt = PromptTemplate(template=template, input_variables=["research_query","context"])
    formatted_prompt = prompt.format(research_query=research_query,context=truncated_research_vector_query_result)
    reading_list = openaichat(formatted_prompt)
    print(reading_list)

    zip_codes = generate_zip_range(user_zip)

    # Save the JSON result as a variable (for category "stay")
    provider_vector_query_result = query_provider_database(provider_query,care_type,zip_codes)

    # Get the truncated JSON object
    truncated_provider_vector_query_result = get_truncated_provider_results(provider_vector_query_result['results'], max_length=500)

    # Print the JSON object
    print(truncated_provider_vector_query_result)

    template = """Mosaic Care is a company that recommends research to people whose parents have been diagnosed with Alzheimer's or other memory problems (these are Mosaic's customers). I have a vector database of the memory care providers.

A customer is looking for {provider_query}.

Below please find chunks of text for the providers most relevant to their search. I'd like you to do the following:
1) Choose 5 out of these 10 chunks that seems most relevant to what the user needs.
2) Present them in a ranked list, including values for: the name of the provider, a one-sentence reason why the customer might want to learn more about them, their rating from Google reviews, their website, and their street address.
3) Title the list "Shortlist of Providers to Research" 

Please ONLY recommend providers from the results below. 

------

DATABASE RESULTS

{context}
"""

    prompt = PromptTemplate(template=template, input_variables=["provider_query","context"])
    formatted_prompt = prompt.format(provider_query=provider_query,context=truncated_provider_vector_query_result)
    provider_list = openaichat(formatted_prompt)

    user_plan = email_opening + '\n' + '\n' + reading_list+ '\n' + '\n' + provider_list

    return jsonify({"user_plan": user_plan})

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
