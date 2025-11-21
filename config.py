class Config:
    """
    Configuration for Claim Compass.
    
    NOTE: In production, these should be loaded from environment variables
    using os.getenv() to avoid committing credentials to version control.
    For this hackathon demo, values are hardcoded for simplicity.
    """
    PROJECT_ID = "gen-lang-client-0379443013"
    DATA_STORE_ID = "benefits-data_1763749786516"
    LOCATION = "us-central1"
    VISION_LOCATION = "us-central1"