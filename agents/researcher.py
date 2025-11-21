from google.cloud import discoveryengine_v1beta as discoveryengine
from google.api_core.client_options import ClientOptions

class ResearcherAgent:
    def __init__(self, project_id, location, data_store_id):
        self.project_id = project_id
        self.location = location
        self.data_store_id = data_store_id
        
        # Setup the Client with regional endpoint
        self.client_options = ClientOptions(
            api_endpoint=f"{location}-discoveryengine.googleapis.com"
        )
        self.client = discoveryengine.SearchServiceClient(client_options=self.client_options)
        self.serving_config = self.client.serving_config_path(
            project=project_id,
            location=location,
            data_store=data_store_id,
            serving_config="default_config",
        )

    def search(self, query):
        """
        Searches the Policy PDF. Returns the AI summary.
        If no summary is generated, falls back to the raw text snippets.
        """
        print(f"🔎 Researcher Agent looking up: '{query}'...")
        
        request = discoveryengine.SearchRequest(
            serving_config=self.serving_config,
            query=query,
            page_size=5, # Increased to catch more context
            content_search_spec={
                "snippet_spec": {"return_snippet": True},
                "summary_spec": {
                    "summary_result_count": 5,
                    "include_citations": True,
                    "ignore_adversarial_query": True
                }
            }
        )

        try:
            response = self.client.search(request)
            
            # STRATEGY 1: Return the fancy AI Summary if it exists
            if response.summary.summary_text:
                return f"AI Summary: {response.summary.summary_text}"

            # STRATEGY 2: Fallback to Raw Snippets (The Fix!)
            # If the AI didn't write a summary, we manually grab the text it found.
            elif response.results:
                print("⚠️ No AI summary generated. Falling back to raw snippets.")
                snippets = []
                for result in response.results:
                    data = result.document.derived_struct_data
                    # Grab the snippets (the highlighted text from the PDF)
                    for snippet in data.get('snippets', []):
                        snippets.append(snippet.get('snippet', ''))
                
                evidence_text = "\n\n".join(snippets)
                return f"Raw Policy Excerpts Found:\n{evidence_text}"
            
            else:
                return "I checked the policy documents, but I couldn't find a specific answer to that."
                
        except Exception as e:
            return f"Error during search: {e}"