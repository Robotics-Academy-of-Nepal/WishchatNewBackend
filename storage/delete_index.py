from azure.search.documents.indexes import SearchIndexClient  
from azure.core.credentials import AzureKeyCredential  

admin_key = "xXdV40I63y7LmusmgAgFqAz5epVlsslUbK8lZKfFJQAzSeDbc3hA" 
endpoint = "https://cg-rag.search.windows.net"

index_client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(admin_key)) 

def delete_index_files(index_name):
    index_client.delete_index(index_name)
    return(f"{index_name} deleted successfully.")


if __name__ == "__main__":
    delete_index_files("semantic-nets-semantic-networks")