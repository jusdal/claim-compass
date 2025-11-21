from agents.researcher import ResearcherAgent
from agents.vision import VisionAgent

# CONFIG
PROJECT_ID = "gen-lang-client-0379443013"
DATA_STORE_ID = "benefits-data_1763749786516"
LOCATION = "us"

def run_test():
    print("--- STARTING CLAIM COMPASS SYSTEM CHECK ---")

    # 1. Test Researcher
    researcher = ResearcherAgent(PROJECT_ID, LOCATION, DATA_STORE_ID)
    policy_answer = researcher.search("What is the deductible for POS A?")
    print(f"\n📘 Policy Answer: {policy_answer}\n")

    # 2. Test Vision (Uncommented!)
    # Make sure the filename matches your screenshot (e.g. fake_bill.png or .jpg)
    vision = VisionAgent(PROJECT_ID, "us-central1") 
    
    # UPDATE THE FILENAME HERE IF NEEDED (e.g. "fake_bill.png")
    bill_data = vision.analyze_bill("fake_bill.png") 
    
    print(f"\n🧾 Bill Data: {bill_data}\n")
    
if __name__ == "__main__":
    run_test()