import asyncio
from google.adk.models.google_llm import Gemini
from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool, google_search
from google.adk.runners import InMemoryRunner
from google.genai import types
from agents.tools import search_policy_documents
# Import Config to access the new variable
from config import Config 
import logging

logger = logging.getLogger(__name__)


class CoordinatorTeam:
    def __init__(self, project_id, location, data_store_id):
        self.project_id = project_id
        self.location = location
        self.data_store_id = data_store_id
        
        # Shared Model
        self.model = Gemini(
            model="gemini-2.5-pro",
            project_id=project_id, 
            location=location
        )

    def _create_policy_researcher(self):
        """Creates the Specialist Researcher who checks ONLY policy documents (Function Tool)."""
        
        def check_insurance_policy(query: str) -> str:
            """Queries the specific insurance policy PDF for coverage limits/exclusions."""
            try:
                # UPDATED: Use Config.DATA_STORE_LOCATION instead of self.location
                return search_policy_documents(
                    query, 
                    self.project_id, 
                    Config.DATA_STORE_LOCATION, 
                    self.data_store_id
                )
            except Exception as e:
                logger.error(f"Error in check_insurance_policy: {e}")
                return f"Error searching policy: {str(e)}"

        return LlmAgent(
            name="PolicyResearcher",
            model=self.model,
            tools=[check_insurance_policy],
            instruction="""
            You are a Medical Policy Analyst.
            1. Use 'check_insurance_policy' to find coverage limits, exclusions, and medical necessity criteria.
            2. Return a bulleted list of POLICY FACTS found in the documents.
            """
        )

    def _create_web_researcher(self):
        """Creates the Specialist Researcher who checks ONLY the web (Search Tool)."""
        return LlmAgent(
            name="WebResearcher",
            model=self.model,
            tools=[google_search],
            instruction="""
            You are a Legal/Medical Researcher.
            1. Use 'google_search' to find federal/state protections (e.g., No Surprises Act) and similar case precedents.
            2. Return a bulleted list of LEGAL/EXTERNAL EVIDENCE with citations.
            """
        )

    def _create_writer(self):
        """Creates the Specialist Writer who drafts the letter."""
        return LlmAgent(
            name="WriterAgent",
            model=self.model,
            instruction="""
            You are a Patient Advocate Writer.
            Take the 'Bill Data', 'Policy Facts', and 'Legal Evidence' provided.
            Draft a formal, professional appeal letter that:
            1. States the patient's case clearly.
            2. Cites specific policy language (from Policy Facts) and laws (from Legal Evidence).
            3. Requests reconsideration with specific action items.
            4. Maintains a professional, respectful tone.
            
            Return ONLY the letter text, formatted and ready to send.
            """
        )

    async def _run_async(self, bill_data_json: str):
        """Async version of the orchestration workflow."""
        # Create the specialized agents
        policy_researcher = self._create_policy_researcher()
        web_researcher = self._create_web_researcher()
        writer = self._create_writer()

        # The Boss Agent
        coordinator = LlmAgent(
            name="ClaimCoordinator",
            model=self.model,
            tools=[AgentTool(policy_researcher), AgentTool(web_researcher), AgentTool(writer)],
            instruction="""
            You are the Appeal Process Manager.
            
            YOUR WORKFLOW:
            1. You have received 'Bill Data' from the Vision Agent.
            2. Call 'PolicyResearcher' to find specific coverage details in the internal documents.
            3. Call 'WebResearcher' to find external legal protections and precedents.
            4. Consolidate the findings.
            5. Call 'WriterAgent' with the 'Bill Data' AND the combined research (Policy + Web) to draft the appeal letter.
            6. Output the final letter from the Writer.
            
            Be methodical. Ensure you have gathered both internal policy info and external legal info before writing.
            """
        )

        # Execute
        runner = InMemoryRunner(agent=coordinator, app_name="claim_compass")
        
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
        try:
            try:
                loop = asyncio.get_running_loop()
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(self._run_async(bill_data_json))
            except RuntimeError:
                return asyncio.run(self._run_async(bill_data_json))
        except Exception as e:
            logger.error(f"Error in coordinator.run: {e}")
            return f"System Error: {str(e)}\n\nPlease check logs for details."