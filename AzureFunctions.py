

import os
import time
import uuid
import streamlit as st
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    SearchFieldDataType,
    SearchField,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
)
from openai import OpenAI
from azure.search.documents import SearchClient
import pandas as pd
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from tqdm import tqdm
from difflib import SequenceMatcher
from io import StringIO

openai_client = None

def uploadSettings(file):
    global openai_client
    bytes_data = file.getvalue()
    print(bytes_data)

    # To convert to a string based IO:
    stringio = StringIO(file.getvalue().decode("utf-8"), newline="\n", )
    print(stringio)

    # To read file as string:
    string_data = stringio.read()
    print(string_data)
    
    settingNames = ["search_endpoint", "search_admin_key", "search_index_name", "OPENAI_API_KEY", "BlobServiceConnectionString"]
    docValues = string_data.split("\n")

    for items in docValues:
        firstEqualsIndex = items.index("=")
        settingName = items[:firstEqualsIndex].replace(" ", "")
        settingValue = items[firstEqualsIndex+1:].replace(" ", "")
        # name, value = items.replace(" ", "").split("=")
        if settingName in settingNames:
            st.session_state[settingName] = settingValue

    if openai_client == None:
        openai_client = OpenAI(api_key=st.session_state["OPENAI_API_KEY"])



def createIndex():
    AzureOpenAiEndPoint = st.session_state['AzureOpenAiEndPoint']
    index_name = st.session_state['search_index_name']
    index_client = SearchIndexClient(endpoint=st.session_state['search_endpoint'], credential=AzureKeyCredential(st.session_state['search_admin_key']))

    fields=[
        SearchField(name="id", type="Edm.String", key=True, filterable=True),
        SearchField(name="text", type="Edm.String", searchable=True, analyzer_name="en.microsoft"),
        SearchField(name="embedding", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), vector_search_dimensions=1536, vector_search_profile_name="myHnswProfile"),
    ]

    vector_search = VectorSearch(  
        algorithms=[  
            HnswAlgorithmConfiguration(name="myHnsw"),
        ],  
        profiles=[  
            VectorSearchProfile(  
                name="myHnswProfile",  
                algorithm_configuration_name="myHnsw",  
                vectorizer_name="myOpenAI",  
            )
        ],  
        vectorizers=[  
            AzureOpenAIVectorizer(  
                vectorizer_name="myOpenAI",  
                kind="azureOpenAI",  
                parameters=AzureOpenAIVectorizerParameters(  
                    resource_url=AzureOpenAiEndPoint,  
                    deployment_name="text-embedding-3-small",
                    model_name="text-embedding-3-small"
                ),
            ),  
        ], 
    )
    index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)

    print(f"Creating index '{index_name}'...")
    # Create the index
    index_client.create_or_update_index(index)
    print(f"Index '{index_name}' created successfully.")

def get_all_documents_from_index():

    search_client = SearchClient(endpoint=st.session_state["search_endpoint"], index_name=st.session_state["search_index_name"], credential=AzureKeyCredential(st.session_state["search_admin_key"]))

    resultData = []
    skip = 0
    top = 500  # Maximum number of documents per request

    while True:
        # Perform a search with an empty query to retrieve all documents
        # Use select="*" to retrieve all retrievable fields
        results = search_client.search(
            search_text="*",
            select="*",
            skip=skip,
            top=top,
            include_total_count=True  # To get the total count of documents
        )

        documents_in_batch = 0
        for i, result in enumerate(results):
            newResult = {
                "ID": result["id"],
                "text": result["text"],
                "score": result["@search.score"],
                "title": "",
                "link": ""
                }
            resultData.append(newResult)
            documents_in_batch += 1

        print(f"Retrieved {documents_in_batch} documents. Total retrieved so far: {len(resultData)}")

        # If there are no more documents in this batch, or we've retrieved all, break the loop
        if documents_in_batch < top:
            break
        
        # Increment skip for the next batch
        skip += top
    
    print(f"\nSuccessfully retrieved a total of {len(resultData)} documents from the index.")
    return pd.DataFrame(resultData)

def get_embedding(text: str) -> list[float]:
    """
    Generates an embedding for the given text using the specified OpenAI model.
    """
    OPENAI_EMBEDDING_MODEL = "text-embedding-3-small" # Match the model used for your documents
    try:
        # For Azure OpenAI, use model=AZURE_OPENAI_DEPLOYMENT_NAME
        response = openai_client.embeddings.create(
            input=text,
            model=OPENAI_EMBEDDING_MODEL
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return []

def perform_vector_search(query_text: str, count: int):
    
    search_client = SearchClient(endpoint=st.session_state["search_endpoint"], index_name=st.session_state["search_index_name"], credential=AzureKeyCredential(st.session_state["search_admin_key"]))

    try:
        print(f"\nGenerating embedding for query: '{query_text}'...")
        query_embedding = get_embedding(query_text)

        if not query_embedding:
            print("Could not generate embedding for the query. Aborting search.")
            return

        # Define the vectorized query.
        # The 'embedding' field in your index is where the vectors are stored.
        # 'fields' specifies which fields to return in the search results.
        vector_query = VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=count, # Number of nearest neighbors to retrieve
            fields="embedding" # The vector field in your index to search against
        )

        # Perform the search.
        # You can combine vector search with keyword search (search_text) if needed.
        results = search_client.search(
            vector_queries=[vector_query],
            select=["id", "text"] # Select the fields you want to retrieve
        )

        found_results = False
        resultData = []
        for i, result in enumerate(results):
            found_results = True
            newResult = {
                "ID": result["id"],
                "text": result["text"],
                "score": result["@search.score"],
                "title": "",
                "link": ""
                }
            resultData.append(newResult)

        if not found_results:
            print("No results found for your query.")
        else:
            return pd.DataFrame(resultData)

    except Exception as e:
        print(f"An error occurred during vector search: {e}")

def perform_ID_search(ID: str):
    allDocs = get_all_documents_from_index()
    try:
        rows = allDocs.index[allDocs["ID"] == ID].to_list()
        if int(len(rows)) != 0:
            details = allDocs.iloc[rows[0]].to_dict()
            return details
        else:
            return None
    except:
        return None

def deleteDocument(ID: str):
    search_client = SearchClient(endpoint=st.session_state["search_endpoint"], index_name=st.session_state["search_index_name"], credential=AzureKeyCredential(st.session_state["search_admin_key"]))
    try:
        # The delete_documents method takes a list of dictionaries, where each dictionary
        # represents a document to be deleted and must contain its key field.
        result = search_client.delete_documents(documents=[{"id": ID}])

        # Check the results of the operation
        for item in result:
            if item.succeeded:
                print(f"Document with key '{item.key}' deleted successfully.")
            else:
                print(f"Failed to delete document with key '{item.key}': {item.error_message}")

    except Exception as e:
        print(f"An error occurred during deletion: {e}")

def searchIndexByText(text):
    # docs = get_all_documents_from_index()
    # for index, row in docs.iterrows():
    #     if text in row["text"]:
    #         return True
    # return False
    search_client = SearchClient(endpoint=st.session_state["search_endpoint"], index_name=st.session_state["search_index_name"], credential=AzureKeyCredential(st.session_state["search_admin_key"]))
    
    try:
        
        results = search_client.search(
            search_text=text,
            select=["id", "text"],
            search_fields=["text"],
            top=3,
        )

        for result in results:
            res = SequenceMatcher(None, text, result["text"]).ratio()
            if res > 0.98:
                return result["id"]
        
        return None

    except Exception as e:
        print(f"An error occurred during text search: {e}")
        return False

def upload_document(text):
    search_client = SearchClient(endpoint=st.session_state["search_endpoint"], index_name=st.session_state["search_index_name"], credential=AzureKeyCredential(st.session_state["search_admin_key"]))
    
    alreadyExists = searchIndexByText(text)
    if alreadyExists is None:
        embedding = get_embedding(text)

        doc_id = str(uuid.uuid4()) # Generate a unique ID if not present
        # Create a dictionary for the document, ensuring 'id' is present
        document = {
            "id": doc_id,
            "text": text,
            "embedding": embedding
        }
        results = search_client.upload_documents(documents=[document])

        # Check for successful uploads
        for result in results:
            if result.succeeded:
                return f"Successfully uploaded to {st.session_state['search_index_name']}."
            else:
                return f"Failed to upload document with key '{result.key}': {result.error_message}"
    else:
        return f"This document or a very similar one already exists: {alreadyExists}"

def getBlobAndIndexDataBackup():
    indexDocs = get_all_documents_from_index()
    
    blob_service_client = BlobServiceClient.from_connection_string(st.session_state["BlobServiceConnectionString"])
    container_client = blob_service_client.get_container_client("chatbot-data")
    blob_list = container_client.list_blobs()

    # blob_client = blob_service_client.get_blob_client(container=container_name, blob="sample-blob.txt")
    # with open(file=os.path.join(r'filepath', 'filename'), mode="wb") as sample_blob:
    #     download_stream = blob_client.download_blob()
    #     sample_blob.write(download_stream.readall())

    blob_list_full = list(container_client.list_blobs())
    total_blobs = len(blob_list_full)

    indexDocs["matched"] = 0
    unmatchedBlobDocs = []
    for blob in tqdm(blob_list_full, total=total_blobs):
        blobClient = container_client.get_blob_client(blob.name)
        downloader = blobClient.download_blob(max_concurrency=1, encoding='UTF-8')
        blob_text = downloader.readall()

        rows = indexDocs.index[indexDocs["text"] == blob_text].to_list()
        if int(len(rows)) != 0:
            indexDocs.loc[rows[0], "matched"] = 1
        else:
            print(f"Could not {blob.name} in Index")
            unmatchedBlobDocs.append({"name": blob.name, "text": blob_text})
    
    return [indexDocs, unmatchedBlobDocs]

def getBlobAndIndexData():
    indexDocs = get_all_documents_from_index()
    indexDocs["matched"] = 0
    unmatchedBlobDocs = []
    try:
        blob_service_client = BlobServiceClient.from_connection_string(st.session_state["BlobServiceConnectionString"])
        container_client = blob_service_client.get_container_client("chatbot-data")

        # First pass: Count the total number of blobs
        # This part will still take time for large containers to get the total.
        # If you can't afford this upfront cost, you'll need a different progress
        # bar strategy (e.g., just showing current item count).
        blob_list_full = list(container_client.list_blobs())
        total_blobs = len(blob_list_full)

        # Yield the total count first, so the frontend can set up the bar
        yield {"status": "total_count", "value": total_blobs}

        # Second pass: Process and yield individual blob data with progress
        processed_count = 0
        for blob in blob_list_full:
            # Simulate work for each blob
            # time.sleep(0.05)
            blobClient = container_client.get_blob_client(blob.name)
            downloader = blobClient.download_blob(max_concurrency=1, encoding='UTF-8')
            blob_text = downloader.readall()
            responce = "Not matched"

            rows = indexDocs.index[indexDocs["text"] == blob_text].to_list()
            if int(len(rows)) != 0:
                indexDocs.loc[rows[0], "matched"] = 1
                responce = "Matched"
            else:
                indexDocs = pd.concat([indexDocs, pd.DataFrame([{"ID": 0, "text": blob_text, "score": 1, "title": blob.name, "link": "", "matched": 2}])], ignore_index=True)
                

            processed_count += 1
            percent_complete = int((processed_count / total_blobs) * 100)

            # Yield progress and the processed data
            yield {
                "status": "in_progress",
                "percent": percent_complete,
                "current_item": blob.name,
                "processed_data": {"name": blob.name, "content": responce}
            }
        
        yield {"status": "completed", "Docs": indexDocs}

    except Exception as e:
        yield {"status": "error", "message": str(e)}

def massUploadFromBlob():
    blob_service_client = BlobServiceClient.from_connection_string(st.session_state["BlobServiceConnectionString"])
    container_client = blob_service_client.get_container_client("chatbot-data")

    blob_list_full = list(container_client.list_blobs())
    total_blobs = len(blob_list_full)

    successfulUploads = 0
    alreadyDoneUploads = 0
    failedUploads = 0
    fails = []
    for blob in tqdm(blob_list_full, total=total_blobs):
        blobClient = container_client.get_blob_client(blob.name)
        downloader = blobClient.download_blob(max_concurrency=1, encoding='UTF-8')
        blob_text = downloader.readall()
        result = upload_document(blob_text)
        if "Successfully" in result:
            successfulUploads += 1
        elif "very similar" in result:
            alreadyDoneUploads += 1
        else:
            failedUploads += 1
            fails.append(blob.name)
    print("Complete\nFailed Uploads: " + str(failedUploads))
    print(fails)