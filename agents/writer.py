import vertexai
from vertexai.generative_models import GenerativeModel

class WriterAgent:
    def __init__(self, project_id, location):
        self.project_id = project_id
        self.location = location
        vertexai.init(project=project_id, location=location)
        # Use the same model that worked for you (1.5-flash or similar)
        self.model = GenerativeModel("gemini-2.5-flash")

    def draft_appeal(self, bill_data, policy_evidence, user_name="None"):
        """
        Synthesizes bill data and policy evidence into a formal appeal letter.
        """
        
        if not user_name:
            user_name = "[PATIENT NAME]"  # Template placeholder
        print(f"✍️ Writer Agent drafting letter for {user_name}...")

        prompt = f"""
        You are an expert Patient Advocate and Medical Billing Specialist. 
        Your goal is to write a formal, firm, but professional insurance appeal letter.

        ### CASE CONTEXT
        **Patient Name:** {user_name}
        **Bill Data:**
        {bill_data}

        **Policy & Legal Evidence Found:**
        {policy_evidence}

        ### INSTRUCTIONS
        1. Write a formal appeal letter to the insurance company.
        2. Explicitly cite the policy evidence provided above. 
        3. If the bill is for Emergency Services (CPT 99281-99285) and the denial is "Out of Network", you MUST cite the "No Surprises Act" which prohibits balance billing for emergency services.
        4. Keep the tone professional and decisive.
        5. Include a placeholder for the "Claim Number" and "Policy Number" if not provided.
        
        Output ONLY the letter text (no markdown chat preamble).
        """

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating letter: {e}"