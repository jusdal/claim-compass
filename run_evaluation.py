#!/usr/bin/env python3
"""
Async evaluation runner for Claim Compass agents.
"""

import os
import sys
import asyncio
from config import Config
from agents.vision import VisionAgent
from agents.coordinator import CoordinatorTeam
from evaluation import AgentEvaluator

# Setup environment
os.environ["GOOGLE_CLOUD_PROJECT"] = Config.PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = Config.LOCATION
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


async def run_evaluation_async():
    """Async version of the evaluation suite."""
    print("\n" + "="*70)
    print("🛡️  CLAIM COMPASS - AGENT EVALUATION SUITE")
    print("="*70)
    print(f"\nProject: {Config.PROJECT_ID}")
    print(f"Location: {Config.LOCATION}")
    print(f"Data Store: {Config.DATA_STORE_ID}\n")
    
    # Initialize components
    print("📦 Initializing agents...")
    try:
        vision_agent = VisionAgent(Config.PROJECT_ID, Config.VISION_LOCATION)
        print("✅ Vision agent initialized")
        
        coordinator_team = CoordinatorTeam(
            Config.PROJECT_ID,
            Config.LOCATION,
            Config.DATA_STORE_ID
        )
        print("✅ Coordinator team initialized")
    except Exception as e:
        print(f"❌ Failed to initialize agents: {e}")
        return 1
    
    # Initialize evaluator
    print("📋 Loading test cases...")
    evaluator = AgentEvaluator()
    print(f"✅ Loaded {len(evaluator.test_cases)} test cases\n")
    
    # Run evaluation (make this async too)
    try:
        results = await evaluator.run_evaluation_suite_async(vision_agent, coordinator_team)
        
        # Print final summary
        print("\n" + "="*70)
        print("✨ EVALUATION COMPLETE")
        print("="*70)
        
        passed = sum(1 for r in results if r.success)
        total = len(results)
        
        if passed == total:
            print(f"🎉 ALL TESTS PASSED ({passed}/{total})")
            return 0
        else:
            print(f"⚠️  {total - passed} TEST(S) FAILED ({passed}/{total} passed)")
            return 1
            
    except Exception as e:
        print(f"\n❌ Evaluation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Entry point that runs the async evaluation."""
    exit_code = asyncio.run(run_evaluation_async())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()