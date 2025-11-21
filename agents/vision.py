import vertexai
import mimetypes
from vertexai.generative_models import GenerativeModel, Part, Image

class VisionAgent:
    def __init__(self, project_id, location):
        self.project_id = project_id
        self.location = location
        
        # Initialize Vertex AI
        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel("gemini-2.5-flash")

    def analyze_bill(self, image_path):
        """
        Reads a medical bill image and extracts structured data.
        """
        print(f"👀 Vision Agent scanning: {image_path}...")

        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith('image/'):
            mime_type = 'image/jpeg'  # Safe fallback
    
        with open(image_path, "rb") as f:
            image_data = f.read()
    
        image_part = Part.from_data(data=image_data, mime_type=mime_type)

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
            response = self.model.generate_content(
                [image_part, prompt]
            )
            return response.text
        except Exception as e:
            return f"Error analyzing bill: {e}"