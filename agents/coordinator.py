import asyncio
from google.adk.models.google_llm import Gemini
from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool, google_search
from google.adk.runners import InMemoryRunner
from google.genai import types
from agents.tools import search_policy_documents
import logging

logger = logging.getLogger(__name__)


class CoordinatorTeam:
    def __init__(self, project_id, location, data_store_id):
        self.project_id = project_id
        self.location = location
        self.data_store_id = data_store_id
        
        # Shared Model (efficient re-use)
        # Use the full model version string for Vertex AI
        self.model = Gemini(
            model="gemini-2.5-pro",
            project_id=project_id, 
            location=location
        )

    def _create_researcher(self):
        """Creates the Specialist Researcher who checks policy & laws."""
        # Wrapper to inject IDs into the custom tool
        def check_insurance_policy(query: str) -> str:
            """Queries the specific insurance policy PDF for coverage limits/exclusions."""
            try:
                return search_policy_documents(
                    query, 
                    self.project_id, 
                    self.location, 
                    self.data_store_id
                )
            except Exception as e:
                logger.error(f"Error in check_insurance_policy: {e}")
                return f"Error searching policy: {str(e)}"

        return LlmAgent(
            name="ResearcherAgent",
            model=self.model,
            tools=[google_search, check_insurance_policy],
            instruction="""
            You are a Medical Billing Researcher.
            1. Use 'check_insurance_policy' to see if the plan covers the specific CPT codes/services.
            2. Use 'google_search' to find federal/state protections (e.g., No Surprises Act).
            3. Return a bulleted list of EVIDENCE found with specific citations.
            4. Be thorough but concise.
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
            Draft a formal, professional appeal letter that:
            1. States the patient's case clearly
            2. Cites specific policy language or laws from the evidence
            3. Requests reconsideration with specific action items
            4. Maintains a professional, respectful tone
            
            Return ONLY the letter text, formatted and ready to send.
            """
        )

    async def _run_async(self, bill_data_json: str):
        """Async version of the orchestration workflow."""
        researcher = self._create_researcher()
        writer = self._create_writer()

        # The Boss Agent
        coordinator = LlmAgent(
            name="ClaimCoordinator",
            model=self.model,
            tools=[AgentTool(researcher), AgentTool(writer)],
            instruction="""
            You are the Appeal Process Manager.
            
            YOUR WORKFLOW:
            1. You have received 'Bill Data' from the Vision Agent.
            2. Call 'ResearcherAgent' to find coverage evidence for the specific CPT codes and services mentioned.
            3. Wait for the research results.
            4. Call 'WriterAgent' with BOTH the 'Bill Data' AND the 'Research Evidence' to draft the appeal letter.
            5. Output the final letter from the Writer.
            
            Be methodical and ensure each step completes before moving to the next.
            """
        )

        # Execute
        runner = InMemoryRunner(agent=coordinator, app_name="claim_compass")
        
        # Create session
        try:
            await runner.session_service.create_session(
                app_name="claim_compass",
                user_id="user",
                session_id="session"
            )
        except Exception as e:
            logger.warning(f"Session creation warning (may already exist): {e}")

        user_msg = types.Content(
            role="user", 
            parts=[types.Part(text=f"Here is the Bill Data:\n\n{bill_data_json}\n\nPlease process this bill and create an appeal letter.")]
        )
        
        final_response = "Processing..."
        
        # Stream events to find the final answer
        try:
            for event in runner.run(
                user_id="user", 
                session_id="session", 
                new_message=user_msg
            ):
                if event.is_final_response() and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            final_response = part.text
                            break
        except Exception as e:
            logger.error(f"Error during agent execution: {e}")
            final_response = f"Error during processing: {str(e)}\n\nPlease check your configuration and try again."
                
        return final_response

    def run(self, bill_data_json: str):
        """
        Orchestrates the entire process:
        1. User provides Bill Data -> Coordinator
        2. Coordinator -> Researcher (Get Evidence)
        3. Coordinator -> Writer (Draft Letter)
        4. Coordinator -> User (Final Output)
        """
        try:
            # Check if there's already an event loop running (e.g., in Streamlit)
            try:
                loop = asyncio.get_running_loop()
                # If we're here, we're already in an async context
                # Create a new task
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(self._run_async(bill_data_json))
            except RuntimeError:
                # No event loop running, we can create one
                return asyncio.run(self._run_async(bill_data_json))
        except Exception as e:
            logger.error(f"Error in coordinator.run: {e}")
            return f"System Error: {str(e)}\n\nPlease check logs for details."