import asyncio
from google.adk.models.google_llm import Gemini
from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool, google_search
from google.adk.runners import InMemoryRunner
from google.genai import types
from agents.tools import search_policy_documents
from config import Config 
import logging
import uuid

# Import observability
from observability import get_observability_manager, AgentPhase

logger = logging.getLogger(__name__)


class CoordinatorTeam:
    def __init__(self, project_id, location, data_store_id):
        self.project_id = project_id
        self.location = location
        self.data_store_id = data_store_id
        
        # Get observability manager
        self.obs = get_observability_manager()
        
        # DON'T initialize the model here - do it per run to avoid event loop issues
        self.model = None

    def _get_or_create_model(self):
        """
        Get the model, creating it fresh if needed.
        This prevents event loop reuse issues across multiple runs.
        """
        # Always create a fresh model for each run
        return Gemini(
            model="gemini-2.5-pro",
            project_id=self.project_id, 
            location=self.location
        )

    def _create_policy_researcher(self):
        """Creates the Specialist Researcher who checks ONLY policy documents (Function Tool)."""
        
        def check_insurance_policy(query: str) -> str:
            """Queries the specific insurance policy PDF for coverage limits/exclusions."""
            # Log tool call
            self.obs.log_tool_call("check_insurance_policy", query, 0)
            
            try:
                result = search_policy_documents(
                    query, 
                    self.project_id, 
                    Config.DATA_STORE_LOCATION, 
                    self.data_store_id
                )
                
                # Log result size
                self.obs.log_tool_call("check_insurance_policy", query, len(result))
                self.obs.log_agent_decision(
            		"PolicyResearcher",
            		f"Search completed",
            		f"Query: '{query[:50]}...' | Found: {len(result)} chars | Success: {len(result) > 0}"
        		)
                return result
                
            except Exception as e:
                logger.error(f"Error in check_insurance_policy: {e}")
                self.obs.log_agent_decision(
            		"PolicyResearcher",
            		"Search failed",
            		f"Query: '{query[:50]}...' | Error: {str(e)}"
        		)
                return f"Error searching policy: {str(e)}"

        return LlmAgent(
            name="PolicyResearcher",
            model=self.model,
            tools=[check_insurance_policy],
			instruction="""
			You are a Medical Policy Analyst.
			1. Search for BROADER terms first (e.g., "physical therapy benefits" not "PT visit 31")
			2. Look for exception processes and appeals language
			3. If specific codes aren't found, search for the SERVICE TYPE
			4. Return ALL relevant policy sections, even if not perfect matches
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

    async def _run_async(self, bill_data_json: str, patient_name: str = "", 
                        patient_zip: str = "", context: str = ""):
        """Async version of the orchestration workflow with observability."""
        
        # Generate trace ID
        trace_id = f"trace_{uuid.uuid4().hex[:8]}"
        self.obs.start_trace(trace_id)
        
        try:
            # CRITICAL FIX: Create a fresh model for this run
            self.model = self._get_or_create_model()
            logger.info(f"Created fresh model for trace {trace_id}")
            
            # Start coordination span
            self.obs.start_span(
                AgentPhase.COORDINATION, 
                "ClaimCoordinator",
                metadata={
                    "bill_length": len(bill_data_json),
                    "has_patient_name": bool(patient_name),
                    "has_context": bool(context)
                }
            )
            
            # Create the specialized agents
            policy_researcher = self._create_policy_researcher()
            web_researcher = self._create_web_researcher()
            writer = self._create_writer()

            # The Boss Agent
            coordinator = LlmAgent(
                name="ClaimCoordinator",
                model=self.model,
                tools=[AgentTool(policy_researcher), AgentTool(web_researcher), AgentTool(writer)],
                instruction=f"""
                You are the Appeal Process Manager.
                
                Patient Information:
                - Name: {patient_name or "Not provided"}
                - Zip Code: {patient_zip or "Not provided"}
                - Additional Context: {context or "None"}
                
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
            
            # Use a unique session ID per run to avoid conflicts
            session_id = f"session_{trace_id}"
            
            try:
                await runner.session_service.create_session(
                    app_name="claim_compass",
                    user_id="user",
                    session_id=session_id
                )
            except Exception as e:
                logger.warning(f"Session creation warning (may already exist): {e}")

            user_msg = types.Content(
                role="user", 
                parts=[types.Part(text=f"Here is the Bill Data:\n\n{bill_data_json}\n\nPlease process this bill and create an appeal letter.")]
            )
            
            final_response = "Processing..."
            
            # Track sub-agent executions
            policy_research_done = False
            web_research_done = False
            
            try:
                for event in runner.run(
                    user_id="user", 
                    session_id=session_id, 
                    new_message=user_msg
                ):
                    # Log agent decisions
                    if hasattr(event, 'agent_name') and hasattr(event, 'content'):
                        agent_name = getattr(event, 'agent_name', 'Unknown')
                        
                        # Track which agents have been called
                        if agent_name == "PolicyResearcher" and not policy_research_done:
                            self.obs.start_span(AgentPhase.POLICY_RESEARCH, "PolicyResearcher")
                            policy_research_done = True
                        elif agent_name == "WebResearcher" and not web_research_done:
                            self.obs.start_span(AgentPhase.WEB_RESEARCH, "WebResearcher")
                            web_research_done = True
                    
                    if event.is_final_response() and event.content:
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                final_response = part.text
                                break
                
                # Close any open spans
                if web_research_done:
                    self.obs.end_span(success=True, result_metadata={"phase": "web_research_complete"})
                if policy_research_done:
                    self.obs.end_span(success=True, result_metadata={"phase": "policy_research_complete"})
                
                # End coordination span
                self.obs.end_span(
                    success=True, 
                    result_metadata={
                        "letter_length": len(final_response),
                        "used_policy_research": policy_research_done,
                        "used_web_research": web_research_done
                    }
                )
                
            except Exception as e:
                logger.error(f"Error during agent execution: {e}", exc_info=True)
                self.obs.end_span(success=False, error=str(e))
                final_response = f"Error during processing: {str(e)}\n\nPlease check your configuration and try again."
                    
            return final_response
            
        except Exception as e:
            logger.error(f"Error in _run_async: {e}", exc_info=True)
            self.obs.end_span(success=False, error=str(e))
            return f"System Error: {str(e)}\n\nPlease check logs for details."
        finally:
            # Always end trace
            self.obs.end_trace()
            
            # CRITICAL FIX: Clean up the model reference
            self.model = None

    def run(self, bill_data_json: str, patient_name: str = "", 
            patient_zip: str = "", context: str = ""):
        """
        Run the coordinator with observability tracking.
        Creates a fresh event loop for each run to avoid loop reuse issues.
        """
        try:
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in a running loop, so we need to use nest_asyncio
                logger.info("Detected running event loop, applying nest_asyncio")
                import nest_asyncio
                nest_asyncio.apply()
                # Run in the current loop
                return asyncio.run(self._run_async(bill_data_json, patient_name, patient_zip, context))
            except RuntimeError:
                # No running loop, create a new one
                logger.info("No running event loop, creating new one")
                return asyncio.run(self._run_async(bill_data_json, patient_name, patient_zip, context))
        except Exception as e:
            logger.error(f"Error in coordinator.run: {e}", exc_info=True)
            if self.obs:
                self.obs.end_span(success=False, error=str(e))
            return f"System Error: {str(e)}\n\nPlease check logs for details."