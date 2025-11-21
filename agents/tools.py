from google.cloud import discoveryengine_v1beta as discoveryengine
from google.api_core.client_options import ClientOptions

def search_policy_documents(query: str, project_id: str, location: str, data_store_id: str) -> str:
    """
    Searches the internal insurance policy PDF for coverage details, exclusions, and limits.
    Use this tool FIRST when asked about specific plan benefits.
    
    Args:
        query: The search query (e.g., "physical therapy coverage limits").
        project_id: The Google Cloud Project ID.
        location: The location (e.g., "global" or "us-central1").
        data_store_id: The Data Store ID for the policy documents.
    """
    client_options = ClientOptions(
        api_endpoint=f"{location}-discoveryengine.googleapis.com"
    )
    client = discoveryengine.SearchServiceClient(client_options=client_options)
    serving_config = client.serving_config_path(
        project=project_id,
        location=location,
        data_store=data_store_id,
        serving_config="default_config",
    )
    
    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=query,
        page_size=3,
        content_search_spec={"snippet_spec": {"return_snippet": True}}
    )
    
    try:
        response = client.search(request)
        snippets = []
        for result in response.results:
            data = result.document.derived_struct_data
            for snippet in data.get('snippets', []):
                snippets.append(snippet.get('snippet', ''))
        
        return "\n\n".join(snippets) if snippets else "No policy documents matched that query."
    except Exception as e:
        return f"Error searching policy docs: {e}"