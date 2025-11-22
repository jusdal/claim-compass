import asyncio
from google.adk.models.google_llm import Gemini
from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool, google_search
from google.adk.runners import InMemoryRunner
from google.genai import types
from agents.tools import search_policy_documents
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
        """Creates the Specialist Researcher who checks ONLY policy documents."""
        
        def check_insurance_policy(query: str) -> str:
            try:
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
        """Creates the Specialist Researcher who checks ONLY the web."""
        return LlmAgent(
            name="WebResearcher",
            model=self.model,
            tools=[google_search],
            instruction="""
            You are a Legal/Medical Researcher.
            1. Use 'google_search' to find federal/state protections.
            2. IMPORTANT: Pay close attention to the 'Patient Zip/State' provided by the Coordinator. 
               Prioritize laws specific to that State over the address on the bill.
            3. Return a bulleted list of LEGAL/EXTERNAL EVIDENCE with citations.
            """
        )

    def _create_writer(self):
        """Creates the Specialist Writer who drafts the letter."""
        return LlmAgent(
            name="WriterAgent",
            model=self.model,
            instruction="""
            You are a Patient Advocate Writer.
            
            DATA HIERARCHY RULES:
            1. The 'VERIFIED PATIENT CONTEXT' provided by the user is the SOURCE OF TRUTH.
            2. If the Name or Address in the 'VERIFIED PATIENT CONTEXT' differs from the 'RAW BILL DATA', YOU MUST USE THE VERIFIED CONTEXT.
            
            Draft a formal, professional appeal letter that:
            1. Is addressed FROM the patient name in the Verified Context.
            2. Cites laws relevant to the State in the Verified Context.
            3. Uses the procedure codes and amounts from the Raw Bill Data.
            4. Requests reconsideration with specific action items.
            
            Return ONLY the letter text, formatted and ready to send.
            """
        )

    async def _run_async(self, bill_data_json: str, patient_name: str = None, patient_zip: str = None, context: str = None):
        """Async version of the orchestration workflow."""
        
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
            
            Your Goal: Orchestrate a perfect appeal letter by resolving data conflicts.
            
            CRITICAL INSTRUCTION ON DATA SOURCES:
            - VERIFIED PATIENT CONTEXT (from UI) is the Master Record. 
            - If the User provides a Name or Zip Code, it OVERRIDES the bill image. 
            
            WORKFLOW:
            1. Analyze the 'VERIFIED PATIENT CONTEXT' to determine the jurisdiction.
            2. Call 'PolicyResearcher' for internal benefits checks.
            3. Call 'WebResearcher' for legal precedents in that jurisdiction.
            4. Call 'WriterAgent' with the processed facts.
            
            FINAL OUTPUT RULE (CRITICAL):
            Your final response to the user MUST BE the exact output from the 'WriterAgent'.
            - Do NOT summarize what you did ("I have drafted the letter...").
            - Do NOT add conversational filler ("Here is the letter...").
            - OUTPUT ONLY THE LETTER TEXT.
            """
        )

        runner = InMemoryRunner(agent=coordinator, app_name="claim_compass")
        
        try:
            await runner.session_service.create_session(app_name="claim_compass", user_id="user", session_id="session")
        except Exception:
            pass

        # --- UPDATED PROMPT CONSTRUCTION ---
        
        prompt_text = "Please process this appeal request.\n\n"
        
        prompt_text += "=== [SECTION 1] VERIFIED PATIENT CONTEXT (SOURCE OF TRUTH) ===\n"
        prompt_text += "Use this data for the Patient Name, Address, and State Jurisdiction.\n"
        prompt_text += f"Patient Name: {patient_name if patient_name else 'Not Provided (Use Bill Data)'}\n"
        prompt_text += f"Patient Zip: {patient_zip if patient_zip else 'Not Provided (Use Bill Data)'}\n"
        prompt_text += f"User Notes: {context if context else 'None'}\n\n"
        
        prompt_text += "=== [SECTION 2] RAW BILL DATA (SCANNED) ===\n"
        prompt_text += "Use this data ONLY for Line Items, CPT Codes, Dates, and Amounts.\n"
        prompt_text += f"{bill_data_json}\n\n"
        
        prompt_text += "INSTRUCTIONS:\n"
        prompt_text += "1. Research the policy and laws.\n"
        prompt_text += "2. Have the WriterAgent draft the letter.\n"
        prompt_text += "3. Your final output must be ONLY the letter text from the WriterAgent."

        user_msg = types.Content(role="user", parts=[types.Part(text=prompt_text)])
        
        final_response = "Processing..."
        
        try:
            for event in runner.run(user_id="user", session_id="session", new_message=user_msg):
                if event.is_final_response() and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            final_response = part.text
                            break
        except Exception as e:
            logger.error(f"Error during agent execution: {e}")
            final_response = f"Error: {str(e)}"
                
        return final_response

    def run(self, bill_data_json: str, patient_name: str = None, patient_zip: str = None, context: str = None):
        """Synchronous wrapper."""
        try:
            try:
                loop = asyncio.get_running_loop()
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(self._run_async(bill_data_json, patient_name, patient_zip, context))
            except RuntimeError:
                return asyncio.run(self._run_async(bill_data_json, patient_name, patient_zip, context))
        except Exception as e:
            logger.error(f"Error: {e}")
            return f"System Error: {str(e)}"