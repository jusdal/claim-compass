from google.cloud import discoveryengine_v1beta as discoveryengine
from google.api_core.client_options import ClientOptions
import logging

logger = logging.getLogger(__name__)


def search_policy_documents(
    query: str, 
    project_id: str, 
    location: str, 
    data_store_id: str
) -> str:
    """
    Searches the internal insurance policy PDF for coverage details, exclusions, and limits.
    Use this tool FIRST when asked about specific plan benefits.
    
    Args:
        query: The search query (e.g., "physical therapy coverage limits").
        project_id: The Google Cloud Project ID.
        location: The location (e.g., "global" or "us-central1").
        data_store_id: The Data Store ID for the policy documents.
        
    Returns:
        String containing relevant snippets from policy documents, or error message.
    """
    logger.info(f"Searching policy documents for: {query}")
    
    try:
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
            page_size=5,  # Get more results for better context
            content_search_spec={
                "snippet_spec": {
                    "return_snippet": True,
                    "max_snippet_count": 3
                },
                "extractive_content_spec": {
                    "max_extractive_answer_count": 3,
                    "max_extractive_segment_count": 3
                }
            }
        )
        
        response = client.search(request)
        snippets = []
        
        for i, result in enumerate(response.results, 1):
            data = result.document.derived_struct_data
            
            # Extract document title/source
            doc_name = result.document.name.split('/')[-1] if result.document.name else f"Document {i}"
            
            # Get snippets
            doc_snippets = data.get('snippets', [])
            for snippet in doc_snippets:
                snippet_text = snippet.get('snippet', '')
                if snippet_text:
                    snippets.append(f"[Source: {doc_name}]\n{snippet_text}")
            
            # Also get extractive answers if available
            extractive_answers = data.get('extractive_answers', [])
            for answer in extractive_answers:
                answer_text = answer.get('content', '')
                if answer_text:
                    snippets.append(f"[Source: {doc_name}]\n{answer_text}")
        
        if snippets:
            result_text = "\n\n---\n\n".join(snippets)
            logger.info(f"Found {len(snippets)} relevant snippets")
            return result_text
        else:
            logger.warning(f"No policy documents matched query: {query}")
            return f"No policy documents matched the query: '{query}'. Try rephrasing or using different keywords."
            
    except Exception as e:
        error_msg = f"Error searching policy documents: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg