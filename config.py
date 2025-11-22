import os


class Config:
    """
    Configuration for Claim Compass.
    
    NOTE: In production, these should be loaded from environment variables
    using os.getenv() to avoid committing credentials to version control.
    For this hackathon demo, values are hardcoded for simplicity.
    """
    # Google Cloud Project Settings
    PROJECT_ID = "gen-lang-client-0379443013"
    DATA_STORE_ID = "benefits-data_1763749786516"
    LOCATION = "us-east1" #where the LLM runs
    VISION_LOCATION = "us-east1"
    
	# 2. Where the Data Store exists (Agent Builder)
    # Try "global" first. If that fails, try "us-central1" or "us-east1"
    DATA_STORE_LOCATION = "us"
    
    # Model Configuration
    # Use versioned model identifiers for Vertex AI
    # Options: gemini-1.5-pro-002, gemini-1.5-flash-002, gemini-1.0-pro-002
    COORDINATOR_MODEL = os.getenv("COORDINATOR_MODEL", "gemini-2.5-pro")
    VISION_MODEL = os.getenv("VISION_MODEL", "gemini-2.5-flash")
    
    # Optional: Model-specific settings
    MAX_OUTPUT_TOKENS = 8192
    TEMPERATURE = 0.7  # 0.0 = deterministic, 1.0 = creative
    
    @classmethod
    def validate(cls):
        """Validates that all required configuration is present."""
        required_fields = ["PROJECT_ID", "DATA_STORE_ID", "LOCATION"]
        missing = [field for field in required_fields if not getattr(cls, field)]
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        print("✓ Configuration validated successfully")
        print(f"  Project: {cls.PROJECT_ID}")
        print(f"  Location: {cls.LOCATION}")
        print(f"  Data Store: {cls.DATA_STORE_ID}")
        print(f"  Coordinator Model: {cls.COORDINATOR_MODEL}")
        print(f"  Vision Model: {cls.VISION_MODEL}")