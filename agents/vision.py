from google import genai
from google.genai import types
import mimetypes
import logging

# Import observability
from observability import get_observability_manager, AgentPhase

logger = logging.getLogger(__name__)


class VisionAgent:
    def __init__(self, project_id, location):
        self.project_id = project_id
        self.location = location
        
        # Get observability manager
        self.obs = get_observability_manager()
        
        # Use the new GenAI Client
        self.client = genai.Client(
            vertexai=True, 
            project=project_id, 
            location=location
        )

    def analyze_bill(self, image_path):
        """
        Reads a medical bill image and extracts structured data with observability tracking.
        
        Args:
            image_path: Path to the bill image file
            
        Returns:
            Structured text containing extracted bill information
        """
        logger.info(f"Vision Agent scanning: {image_path}")
        
        # Start vision span
        self.obs.start_span(
            AgentPhase.VISION,
            "VisionAgent",
            metadata={"image_path": image_path}
        )

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith('image/'):
            mime_type = 'image/jpeg'
            logger.warning(f"Could not determine MIME type, defaulting to {mime_type}")
    
        # Read image bytes
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
        except Exception as e:
            logger.error(f"Error reading image file: {e}")
            self.obs.end_span(success=False, error=f"File read error: {str(e)}")
            return f"Error reading image file: {str(e)}"
            
        prompt = """
        You are an expert Medical Biller analyzing a medical bill or insurance document.
        
        Extract ALL of the following information in a clear, structured format:
        
        1. **Provider Name**: Name of the medical facility or doctor
        2. **Date of Service**: When the service was provided
        3. **Total Billed Amount**: The total amount charged
        4. **Patient Responsibility**: Amount the patient needs to pay
        5. **Insurance Paid**: Amount insurance company paid (if shown)
        6. **CPT Codes**: List all procedure codes found (with descriptions if visible)
        7. **Denial Information**: 
           - Is this a denial? (Yes/No)
           - Denial reason (if shown)
           - Denial code (if shown)
        8. **Additional Details**: Any other relevant billing information
        
        Format your response as clear, structured text (NOT as a code block).
        If any information is not visible in the image, state "Not visible" for that field.
        Be thorough and extract every piece of information you can see.
        """

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
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
            
            if response and response.text:
                logger.info("Vision analysis successful")
                
                # Extract metadata for observability
                result_length = len(response.text)
                cpt_count = response.text.count("CPT") + response.text.count("cpt")
                has_denial = "denial" in response.text.lower()
                
                # End span with success
                self.obs.end_span(
                    success=True,
                    result_metadata={
                        "output_length": result_length,
                        "cpt_codes_found": cpt_count,
                        "denial_detected": has_denial
                    }
                )
                
                return response.text
            else:
                logger.error("Empty response from vision model")
                self.obs.end_span(success=False, error="Empty model response")
                return "Error: No response from vision model. The image may be unclear or invalid."
                
        except Exception as e:
            logger.error(f"Error analyzing bill with vision model: {e}", exc_info=True)
            self.obs.end_span(success=False, error=str(e))
            return f"Error analyzing bill: {str(e)}\n\nPlease ensure the image is clear and try again."