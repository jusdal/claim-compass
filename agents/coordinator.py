import asyncio  # <--- ADD THIS IMPORT
from google.adk.models.google_llm import Gemini
from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool, google_search
from google.adk.runners import InMemoryRunner
from google.genai import types
from agents.tools import search_policy_documents

class CoordinatorTeam:
    def __init__(self, project_id, location, data_store_id):
        self.project_id = project_id
        self.location = location
        self.data_store_id = data_store_id
        
        # Shared Model (efficient re-use)
        self.model = Gemini(model="gemini-1.5-pro", project_id=project_id, location=location)

    def _create_researcher(self):
        """Creates the Specialist Researcher who checks policy & laws."""
        # Wrapper to inject IDs into the custom tool
        def check_insurance_policy(query: str) -> str:
            """Queries the specific insurance policy PDF for coverage limits/exclusions."""
            return search_policy_documents(query, self.project_id, self.location, self.data_store_id)

        return LlmAgent(
            name="ResearcherAgent",
            model=self.model,
            tools=[google_search, check_insurance_policy], # Access to both Web & PDF
            instruction="""
            You are a Medical Billing Researcher.
            1. Use 'check_insurance_policy' to see if the plan covers the specific CPT codes/services.
            2. Use 'google_search' to find federal/state protections (e.g., No Surprises Act).
            3. Return a bulleted list of EVIDENCE found.
            """
        )

    def _create_writer(self):
        """Creates the Specialist Writer who drafts the letter."""
        return LlmAgent(
            name="WriterAgent",
            model=self.model,
            instruction="""
            You are a Patient Advocate Writer.
            Take the 'Bill Data' and 'Research Evidence' provided.
            Draft a formal, professional appeal letter. 
            Cite the policy language or laws found in the evidence.
            Return ONLY the letter text.
            """
        )

    def run(self, bill_data_json: str):
        """
        Orchestrates the entire process:
        1. User provides Bill Data -> Coordinator
        2. Coordinator -> Researcher (Get Evidence)
        3. Coordinator -> Writer (Draft Letter)
        4. Coordinator -> User (Final Output)
        """
        
        researcher = self._create_researcher()
        writer = self._create_writer()

        # The Boss Agent
        coordinator = LlmAgent(
            name="ClaimCoordinator",
            model=self.model,
            # WRAP SUB-AGENTS AS TOOLS
            tools=[AgentTool(researcher), AgentTool(writer)],
            instruction="""
            You are the Appeal Process Manager.
            
            YOUR WORKFLOW:
            1. You have received 'Bill Data'.
            2. Call 'ResearcherAgent' to find coverage evidence for this specific bill.
            3. Call 'WriterAgent' with the 'Bill Data' AND the 'Research Evidence' to draft the letter.
            4. Output the final letter from the Writer.
            """
        )

        # Execute
        runner = InMemoryRunner(agent=coordinator, app_name="claim_compass")
        
        # --- FIX START ---
        # Explicitly run the async session creation
        asyncio.run(runner.session_service.create_session(
            app_name="claim_compass",
            user_id="user",
            session_id="session"
        ))
        # --- FIX END ---

        user_msg = types.Content(role="user", parts=[types.Part(text=f"Here is the Bill Data: {bill_data_json}")])
        
        final_response = "Processing..."
        
        # Stream events to find the final answer
        for event in runner.run(user_id="user", session_id="session", new_message=user_msg):
            if event.is_final_response() and event.content:
                final_response = event.content.parts[0].text
                
        return final_response