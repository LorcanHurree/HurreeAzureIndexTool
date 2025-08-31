import streamlit as st
import AzureFunctions
import pandas as pd

apptitle = 'ChatbotDocs'

st.set_page_config(page_title=apptitle, page_icon=":eyeglasses:")
st.set_page_config(layout="wide")

# -- Default detector list
CurrentUI = ['SearchIndex','uploadDocuemnt', 'V1']

# Title the app
st.title('Chatbot file viewer')

st.markdown("""
 * Use the menu at left to set index names and API keys
 * Or upload them from a settings file
""")

if "search_endpoint" not in st.session_state:
    st.session_state['search_endpoint'] = ""
    st.session_state['search_admin_key'] = ""
    st.session_state['search_index_name'] = ""
    st.session_state['OPENAI_API_KEY'] = ""
    st.session_state['BlobServiceConnectionString'] = ""

st.sidebar.markdown("# API keys")

#-- Set time by GPS or event
st.sidebar.markdown("## ENV variables")
st.sidebar.markdown("Please upload the text file containing the API keys.")
uploaded_file = st.sidebar.file_uploader("Choose a file", accept_multiple_files=False, type="txt", )
if uploaded_file is not None:
    AzureFunctions.uploadSettings(uploaded_file)
    with st.sidebar.container(border=True, height=None):
        st.markdown(f"## Search Service Endpoint\n{st.session_state['search_endpoint']}")
        st.markdown(f"## Search Service Admin Key\n{st.session_state['search_admin_key']}")
        st.markdown(f"## Search Service Index Name\n{st.session_state['search_index_name']}")
        st.markdown(f"## OpenAI API key\n{st.session_state['OPENAI_API_KEY']}")
        st.markdown(f"## Blob storage connection string\n{st.session_state['BlobServiceConnectionString']}")
    
    # searchServiceAdminKey = st.sidebar.markdown("Search Service Admin Key", value=st.session_state['search_admin_key'], key="search_admin_key", help="The admin key for the search service. This should be under the key tab of the search service.")
    # searchServiceIndexName= st.sidebar.markdown("Search Service Index Name", value=st.session_state['search_index_name'], key="search_index_name", help="The name of the index being used/created.")
    # OpenAIKey= st.sidebar.markdown("OpenAI API key", value=st.session_state['OPENAI_API_KEY'], key="OPENAI_API_KEY")
    # BlobConnectionString= st.sidebar.markdown("Blob storage connection string", value=st.session_state['BlobServiceConnectionString'], key="BlobServiceConnectionString", help="The connection string for the blob storage that can be found in the keys section under key 1.")


if 'resultDF' not in st.session_state:
    st.session_state['resultDF'] = None
    st.session_state['newSearch'] = False

if 'comparisonData' not in st.session_state:
    st.session_state['comparisonData'] = None

@st.dialog("Cast your vote")
def showDocument(index:int):
    print(index)
    df = st.session_state['resultDF']
    print(df.at[index, "ID"])
    st.text_area("ID", df.at[index, "ID"], height=100)
    st.text_area("Title", df.at[index, "title"], height=100)
    st.text_area("Text", df.at[index, "text"], height=500)
    st.text_area("Score", df.at[index, "score"], height=100)
    st.text_area("Link", df.at[index, "link"], height=100)

@st.dialog("Delete file?")
def deleteDocument(details):
    st.text_area("ID", details["ID"], height=100)
    st.text_area("Title", details["title"], height=100)
    st.text_area("Text", details["text"], height=500)
    st.text_area("Score", details["score"], height=100)
    st.text_area("Link", details["link"], height=100)
    st.markdown("# ARE YOU SURE YOU WANT TO DELETE THIS FILE!")
    if st.button("Delete"):
        AzureFunctions.deleteDocument(details["ID"])
        st.rerun()

def processDocTitles(df):
    for index, row in df.iterrows():
        text:str = row['text']
        if text.startswith("This document depicts "):
            titleStart = text.index("data points for the")+19
            titleEnd = text.index("under")
            title2Start = titleEnd+11
            title2End = text.index("category", title2Start)
            completeTitle = text[titleStart:titleEnd] + text[title2Start:title2End]
            df.loc[index, "title"] = completeTitle
        elif text.startswith("This is a webpage"):
            titleStart = text.index("\n")+13
            titleEnd = text.index("\n", titleStart)
            linkStart = titleEnd+5
            linkEnd = text.index("\n", linkStart+2)
            title = str(text[titleStart:titleEnd]).strip()
            link = str(text[linkStart:linkEnd]).strip()
            text = str(text[linkEnd:]).strip()
            df.loc[index, "text"] = text
            df.loc[index, "title"] = title
            df.loc[index, "link"] = link
        elif text.startswith("This document is a description of the website"):
            titleStart = len(str("This document is a description of the website "))
            titleEnd = text.index(",", titleStart)
            title = str(text[titleStart:titleEnd]).strip() + " Website Description."
            df.loc[index, "title"] = title
    return df

def showResults():
    resultDF = st.session_state['resultDF']
    if resultDF is not None:
        if st.session_state['newSearch'] == True:
            resultDF = processDocTitles(resultDF)
            st.session_state['newSearch'] = False

        resultCount = resultDF.shape[0]
        if resultCount > 10:
            st.write(f"Number of resuls: {resultCount}")
        buttonID = 0
        with st.container(border=True):
            for index, row in resultDF.iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns(3)
                    col1.markdown("Title:\n"+row["title"])
                    col2.markdown("Score:\n"+str(row["score"]))
                    col3.button("View Result", use_container_width=True, on_click=showDocument, args=[index], key=buttonID)
                    buttonID += 1
    else:
        with st.container(border=True):
            st.write("No current results")

def drawSearchPage():
    st.text("Search index using the same method as the chatbot does.\nUse this to see the information the chatbot has to work with when answering spcific queries\nLeave the search bar blank if you want to see all documents currently in the index.")
    searchQuery = st.text_input("Search query")
    docCount = st.slider("Retrive top n documents", 3, 10, 3)

    if st.button("Search"):
        st.session_state['resultDF'] = None
        if searchQuery != '':
            resultDF = AzureFunctions.perform_vector_search(searchQuery, docCount)
        else:
            resultDF = AzureFunctions.get_all_documents_from_index()
        st.session_state['resultDF'] = resultDF
        st.session_state['newSearch'] = True

    showResults()
    
def drawDeletePage():
    st.text("Insert document ID you want to delete.")
    searchQuery = st.text_input("Document ID")
    if st.button("Find document"):

        if searchQuery != '':
            resultDetails = AzureFunctions.perform_ID_search(searchQuery)
            if resultDetails is not None:
                deleteDocument(resultDetails)
                st.write(f"{searchQuery} deleted.")
            else:
                st.write("No document found.")

def drawUploadPage():
    st.text("This page is for adding a new text file to the index.")
    st.text("Enter the text below that you would like added to the index.")
    st.text("The chatbot will have access to it immediately so you can test it eiter through the chatbot or the search page.")
    data = st.text_area("Document content", height=300)
    if st.button("Upload"):
        result = AzureFunctions.upload_document(data)
        st.markdown(result)
    st.text("")
    st.text("This button is for mass uploading from the blob storage to the index.\nThis may take some time as it has to check hundreds of documents against what is already in the index.\nThere is a check so the same file is not uploaded twice.")
    if st.button("Mass upload"):
        AzureFunctions.massUploadFromBlob()

def drawCompareTab():
    st.text("Press the button to copare the blob storage to the current index")
    if st.button("Compare"):
        st.session_state['comparisonData'] = None
        info_placeholder = st.empty()
        progress_bar_placeholder = st.empty()
        progress_text_placeholder = st.empty()

        # List to store all processed data
        all_processed_data = []

        # --- Call the backend generator function ---
        generator = AzureFunctions.getBlobAndIndexData()

        total_blobs = 0
        # docs, unmatchedBlobs = AzureFunctions.compareBlobToIndex()

        try:
            for update in generator:
                if update["status"] == "total_count":
                    total_blobs = update["value"]
                    info_placeholder.info(f"Found {total_blobs} blobs to process.")
                    # Initialize the actual progress bar
                    my_bar = progress_bar_placeholder.progress(0)
                    progress_text_placeholder.text("Starting processing...")
                
                elif update["status"] == "in_progress":
                    percent = update["percent"]
                    current_item = update["current_item"]
                    processed_data = update["processed_data"]

                    # Update Streamlit elements
                    my_bar.progress(percent)
                    progress_text_placeholder.text(f"Processing: {current_item} ({percent}%)")
                    
                    all_processed_data.append(processed_data) # Store the data

                elif update["status"] == "completed":
                    my_bar.empty() # Clear the progress bar
                    progress_text_placeholder.empty() # Clear the text
                    info_placeholder.success(f"Finished processing all {total_blobs} blobs!")

                    st.session_state['comparisonData'] = update["Docs"]

                elif update["status"] == "error":
                    info_placeholder.error(f"Error during processing: {update['message']}")
                    if 'my_bar' in locals(): # Check if bar was initialized
                        my_bar.empty()
                    progress_text_placeholder.empty()
                    break # Stop processing on error

        except Exception as e:
            info_placeholder.error(f"An unexpected error occurred in Streamlit: {e}")
            if 'my_bar' in locals(): # Check if bar was initialized
                my_bar.empty()
            progress_text_placeholder.empty()

        # print(docs["matched"].value_counts().get(1))
        # print(docs["matched"].value_counts().get(0))
        # print(len(unmatchedBlobs))
    if isinstance(st.session_state['comparisonData'], pd.DataFrame):
        docs = st.session_state['comparisonData']

        # docs = processDocTitles(docs)
        
        MatchedCount = docs["matched"].value_counts().get(1)
        IndexOnlyCount = docs["matched"].value_counts().get(0)
        blobOnlyCount = docs["matched"].value_counts().get(2)

        MatchedCount = 0 if MatchedCount == None else MatchedCount
        IndexOnlyCount = 0 if IndexOnlyCount == None else IndexOnlyCount
        blobOnlyCount = 0 if blobOnlyCount == None else blobOnlyCount

        st.subheader("Processed Data Summary:")
        st.write(f"- **Number of documents that are in both the index and document storage**: \n{MatchedCount}")
        st.write(f"- **Number of documents that are only in the index**: \n{IndexOnlyCount}")
        st.write(f"- **Number of documents that are only in the blob**: \n{blobOnlyCount}")
        with st.expander("In both Index and blob"):
            matchedRows = docs.loc[docs["matched"] == 1]
            for index, row in matchedRows.iterrows():
                with st.container(border=True):
                    st.markdown(row["text"])
        with st.expander("Just in the Index"):
            matchedRows = docs.loc[docs["matched"] == 0]
            for index, row in matchedRows.iterrows():
                with st.container(border=True):
                    st.markdown(row["text"])
        with st.expander("Just in the Blob"):
            matchedRows = docs.loc[docs["matched"] == 2]
            for index, row in matchedRows.iterrows():
                with st.container(border=True):
                    st.markdown(row["text"])


SearchTab, UploadTab, DeleteTab, CompareTab = st.tabs(["Search", "Upload", "Delete", "Compare"])

with SearchTab:
    drawSearchPage()
with DeleteTab:
    drawDeletePage()
with UploadTab:
    drawUploadPage()
with CompareTab:
    drawCompareTab()
