from google import genai
from google.genai import types
import mimetypes

class VisionAgent:
    def __init__(self, project_id, location):
        self.project_id = project_id
        self.location = location
        
        # Use the new GenAI Client
        self.client = genai.Client(
            vertexai=True, 
            project=project_id, 
            location=location
        )

    def analyze_bill(self, image_path):
        """
        Reads a medical bill image and extracts structured data.
        """
        print(f"👀 Vision Agent scanning: {image_path}...")

        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith('image/'):
            mime_type = 'image/jpeg'
    
        # Read image bytes
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            
        prompt = """
        You are an expert Medical Biller. Analyze this bill image.
        Extract the following into a clean JSON-like format (no markdown code blocks, just text):
        1. Provider Name
        2. Date of Service
        3. Total Billed Amount
        4. List of CPT Codes (procedure codes) found
        5. Denial Reason (if visible)
        """

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=prompt),
                            types.Part(
                                inline_data=types.Blob(
                                    mime_type=mime_type,
                                    data=image_bytes
                                )
                            )
                        ]
                    )
                ]
            )
            return response.text
        except Exception as e:
            return f"Error analyzing bill: {e}"