from google.cloud import discoveryengine_v1beta as discoveryengine
from google.api_core.client_options import ClientOptions

# --- CONFIGURATION ---
PROJECT_ID = "gen-lang-client-0379443013"  # <--- PASTE YOUR ID HERE
DATA_STORE_ID = "benefits-data_1763749786516"
LOCATION = "us"

def test_search():
    client_options = ClientOptions(api_endpoint="us-discoveryengine.googleapis.com")
    client = discoveryengine.SearchServiceClient(client_options=client_options)
    serving_config = client.serving_config_path(
        project=PROJECT_ID,
        location=LOCATION,
        data_store=DATA_STORE_ID,
        serving_config="default_config",
    )

    print(f"🔎 Connecting to Data Store: {DATA_STORE_ID}...")
    
    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query="What is the copay for emergency room?",
        page_size=1,
        content_search_spec={
            "snippet_spec": {"return_snippet": True},
            "summary_spec": {"summary_result_count": 1}
        }
    )

    try:
        response = client.search(request)
        print("\n✅ SUCCESS! Connection established.\n")
        
        if response.summary.summary_text:
            print(f"🤖 AI Answer: {response.summary.summary_text}")
        else:
            print("⚠️ Connected, but no summary returned. (Data might still be indexing)")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    test_search()