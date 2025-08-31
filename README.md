
# Internal AI Document Manager

This is a Streamlit tool for finding, adding and removing documents from the chatbot index. The chatbox index is where the chatbot pulls its information from when responding to user inquiries.

Some background information. The chatbot uses an index on azure that contains documents along with all their relevant vectors that allow for accurate searching. 
All of the documents currently in the index are pulled from a document storage service on Azure called a blob. The blob just stores the text so what this tool does is add vectors to the text when uploading it to the index.
Without adding vectors to the text when uploading it to the index, the index can only search using keywords which can be inaccurate and provide bad results to the chatbot resulting in inaccurate answers or the chatbot just not answering at all.

## Tools
The 4 main tools are:

### Search
This tab allows you to search the index to see what the chatbot sees when it is trying to find information. So if the customer is getting bad responses about forecasting, try searching forecasting in here and see if any useful documents come up. If no useful documents show then it explains why the chatbot gave bad responses or just started guessing.

### Upload
Mostly self explanatory. You can add documents straight into the index so the chatbot can see them. The uploaded file should be visible to the chatbot immediately so you should be able to test the change to the chatbot's responses.

The Mass Upload takes all of the documents in the Blob storage and attempts to upload them all to the index. This is a quick way to make sure the index is up to date with any new documents that were added to the blob.
There are checks to stop the same document being uploaded twice so there’s no need to worry if you’re running it multiple times.


### Delete
This requires the document's exact ID, which you can get from the search tab. It will show a window with the document contents to make sure you’re deleting the right one. This only affects the index and not the storage blob.

### Compare
This checks the difference between the index and the storage blob. It will show three categories:
Documents that are in both the storage blob and index
Documents that are only in the storage blob and not the index
Documents that are only in the index and not the storage blob
Allows you to check if the index is up to date and if there are files that have been added to the index but not backed up in the storage blob.