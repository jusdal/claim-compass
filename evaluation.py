"""
Agent Evaluation Suite for Claim Compass.
Tests agent performance on synthetic and real-world medical bills.
"""

import json
import time
import warnings
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import re
import logging

from google import genai
from config import Config

# Suppress asyncio warnings about pending tasks on exit
warnings.filterwarnings("ignore", category=RuntimeWarning, module="asyncio")

logger = logging.getLogger(__name__)


@dataclass
class EvaluationCase:
    """A single test case for agent evaluation."""
    case_id: str
    name: str
    description: str
    input_bill_data: str  # Simulated vision agent output
    expected_outputs: Dict[str, Any]  # What we expect to find
    tags: List[str]  # e.g., ["emergency", "out_of_network", "no_surprises_act"]
    insurance_provider: str = "General Policy" # <--- ADDED THIS


@dataclass
class EvaluationResult:
    """Results from evaluating a single case."""
    case_id: str
    timestamp: str
    duration_seconds: float
    success: bool
    
    # Scoring
    vision_score: float  # 0-1: Did vision extract correctly?
    research_score: float  # 0-1: Did research find relevant evidence?
    letter_score: float  # 0-1: Is the letter well-formatted and persuasive?
    overall_score: float  # 0-1: Combined score
    
    # Details
    vision_errors: List[str]
    research_errors: List[str]
    letter_errors: List[str]
    
    # Outputs
    generated_letter: str
    agent_metadata: Dict[str, Any]


class AgentEvaluator:
    """
    Evaluates agent performance across multiple test cases.
    Measures accuracy, completeness, and quality.
    """
    
    def __init__(self, results_dir: str = "evaluation_results"):
        """Initialize evaluator with results directory."""
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)
        self.test_cases = self._load_test_cases()

        #Initialize the Judge Model
        self.client = genai.Client(
            vertexai=True, 
            project=Config.PROJECT_ID, 
            location=Config.LOCATION
        )
        
    def _get_test_image_path(self, case_id: str) -> Path:
        """Map test case to its corresponding image."""
        image_map = {
            "case_001": "case_001_emergency_room.png",
            "case_002": "case_002_physical_therapy.png", 
            "case_003": "case_003_cancer_treatment.png"
        }
    
        if case_id not in image_map:
            raise ValueError(f"No test image found for case_id: {case_id}")
        return Path("test_images") / image_map[case_id]
    
    def _load_test_cases(self) -> List[EvaluationCase]:
        """Load predefined test cases."""
        return [
            EvaluationCase(
                case_id="case_001",
                name="Emergency Room Out-of-Network",
                insurance_provider="Syracuse University", # <--- SPECIFIC PROVIDER
                description="Patient received emergency care at out-of-network facility",
                input_bill_data="""...""", # Keeping for reference/scoring logic
                expected_outputs={
                    "should_mention_no_surprises_act": True,
                    "should_cite_policy": True,
                    "should_request_in_network_rate": True,
                    "expected_cpt_codes": ["99285", "70450", "36415", "80053"],
                    "key_phrases": ["emergency", "no surprises act", "out-of-network", "good faith estimate"]
                },
                tags=["emergency", "out_of_network", "no_surprises_act", "federal_protection"]
            ),
            
            EvaluationCase(
                case_id="case_002",
                name="Physical Therapy Benefit Limit",
                insurance_provider="Rochester Institute of Technology", # <--- SPECIFIC PROVIDER
                description="Patient exceeded annual PT visit limit",
                input_bill_data="""...""",
                expected_outputs={
                    "should_check_policy_limits": True,
                    "should_mention_medical_necessity": True,
                    "should_request_exception": True,
                    "expected_cpt_codes": ["97110", "97112", "97140"],
                    "key_phrases": ["benefit limit", "medical necessity", "exception", "appeal"]
                },
                tags=["benefit_limit", "physical_therapy", "medical_necessity"]
            ),
            
            EvaluationCase(
                case_id="case_003",
                name="Experimental Treatment Denial",
                insurance_provider="Kaiser Permanente", # <--- SPECIFIC PROVIDER
                description="Denied for experimental/investigational treatment",
                input_bill_data="""...""",
                expected_outputs={
                    "should_research_fda_status": True,
                    "should_mention_clinical_trials": True,
                    "should_cite_medical_literature": True,
                    "expected_cpt_codes": ["96413", "J9999"],
                    "key_phrases": ["experimental", "clinical trial", "medical necessity", "standard of care"]
                },
                tags=["experimental", "cancer", "high_cost", "clinical_trial"]
            )
        ]
    
    def evaluate_vision_extraction(self, case: EvaluationCase, bill_data: str) -> Tuple[float, List[str]]:
        """Evaluate vision agent's extraction accuracy."""
        errors = []
        score_components = []
        
        # Check if expected CPT codes were extracted
        expected_codes = case.expected_outputs.get("expected_cpt_codes", [])
        found_codes = []
        for code in expected_codes:
            if code in bill_data:
                found_codes.append(code)
        
        if expected_codes:
            code_accuracy = len(found_codes) / len(expected_codes)
            score_components.append(code_accuracy)
            if code_accuracy < 1.0:
                missing = set(expected_codes) - set(found_codes)
                errors.append(f"Missing CPT codes: {missing}")
        
        # Simple checks based on tags (Robust fallback)
        if "Total Billed Amount" in str(case.input_bill_data): # Simple string check
             if "billed" not in bill_data.lower() and "amount" not in bill_data.lower():
                errors.append("Total billed amount not extracted")
                score_components.append(0.0)
             else:
                score_components.append(1.0)

        if "Denial Information" in str(case.input_bill_data):
            if "denial" not in bill_data.lower():
                errors.append("Denial information not extracted")
                score_components.append(0.0)
            else:
                score_components.append(1.0)
        
        final_score = sum(score_components) / len(score_components) if score_components else 0.0
        return final_score, errors
    
    def evaluate_research_quality(self, case: EvaluationCase, letter: str, 
                                   research_metadata: Dict) -> Tuple[float, List[str]]:
        """Evaluate research agent's evidence gathering."""
        errors = []
        score_components = []
        
        # Check for No Surprises Act
        if case.expected_outputs.get("should_mention_no_surprises_act"):
            if "no surprises act" in letter.lower() or "nsa" in letter.lower():
                score_components.append(1.0)
            else:
                errors.append("Should cite No Surprises Act")
                score_components.append(0.0)
        
        # Check for policy citations
        if case.expected_outputs.get("should_cite_policy"):
            has_policy_ref = any(phrase in letter.lower() for phrase in 
                                ["policy", "coverage", "benefit", "plan document"])
            if has_policy_ref:
                score_components.append(1.0)
            else:
                errors.append("Missing specific policy citations")
                score_components.append(0.5)
        
        # Check for key phrases
        expected_phrases = case.expected_outputs.get("key_phrases", [])
        found_phrases = [p for p in expected_phrases if p.lower() in letter.lower()]
        if expected_phrases:
            phrase_score = len(found_phrases) / len(expected_phrases)
            score_components.append(phrase_score)
        
        final_score = sum(score_components) / len(score_components) if score_components else 0.0
        return final_score, errors
    
    def evaluate_letter_quality(self, case: EvaluationCase, letter: str) -> Tuple[float, List[str]]:
        """Evaluate the quality of the generated appeal letter."""
        errors = []
        score_components = []
        
        # Check structure
        has_greeting = any(word in letter for word in ["Dear", "To Whom"])
        has_closing = any(word in letter for word in ["Sincerely", "Respectfully", "Regards"])
        structure_score = (has_greeting + has_closing) / 2
        score_components.append(structure_score)
        
        if not has_greeting: errors.append("Missing greeting")
        if not has_closing: errors.append("Missing closing")
        
        # Check length
        word_count = len(letter.split())
        if word_count < 100:
            errors.append(f"Letter too short ({word_count} words)")
            score_components.append(0.5)
        else:
            score_components.append(1.0)
        
        # Check for clear ask
        has_clear_ask = any(phrase in letter.lower() for phrase in 
                           ["request", "ask", "reconsider", "appeal", "review"])
        if has_clear_ask:
            score_components.append(1.0)
        else:
            errors.append("Missing clear request for action")
            score_components.append(0.5)
        
        final_score = sum(score_components) / len(score_components) if score_components else 0.0
        return final_score, errors
    
    def evaluate_with_llm_judge(self, case: EvaluationCase, letter: str) -> Tuple[float, str]:
        """
        Uses Gemini to judge the quality, tone, and persuasiveness of the letter.
        Returns: (score 0.0-1.0, reasoning)
        """
        prompt = f"""
        You are an expert Medical Billing Advocate and Legal Auditor.
        Evaluate the following appeal letter based on the provided scenario.

        **SCENARIO:**
        - Case: {case.name}
        - Description: {case.description}
        - Provider Context: {case.insurance_provider}
        - Mandatory Elements: {json.dumps(case.expected_outputs)}

        **GENERATED LETTER:**
        {letter}

        **EVALUATION RUBRIC:**
        Score the letter from 0 to 100 on these criteria:
        1. **Tone (25pts):** Is it professional, firm, yet respectful?
        2. **Clarity (25pts):** Does it clearly state the error and the requested remedy?
        3. **Evidence (25pts):** Does it cite specific laws (e.g. No Surprises Act) or policy sections appropriately?
        4. **Completeness (25pts):** Are all placeholders filled? Does it include account numbers and dates?

        Return valid JSON:
        {{
            "score": <0-100>,
            "reasoning": "<One sentence explanation of the score>"
        }}
        """

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            result = json.loads(response.text)
            
            # Normalize score to 0.0 - 1.0
            score = result.get("score", 0) / 100.0
            reasoning = result.get("reasoning", "No reasoning provided")
            
            return score, reasoning
            
        except Exception as e:
            logger.error(f"LLM Judge failed: {e}")
            return 0.0, f"Judge Error: {str(e)}"
    
    def evaluate_case(self, case: EvaluationCase, generated_letter: str, 
                     vision_output: str, research_metadata: Dict = None) -> EvaluationResult:
        """Evaluate a single test case with LLM-as-a-Judge."""
        start_time = time.time()
        research_metadata = research_metadata or {}
        
        # 1. Rule-based checks (Fast & Deterministic)
        vision_score, vision_errors = self.evaluate_vision_extraction(case, vision_output)
        research_score, research_errors = self.evaluate_research_quality(case, generated_letter, research_metadata)
        
        # 2. LLM Judge (Qualitative & nuanced)
        # Replaces the old simple "letter_score" rule-based check
        letter_score, judge_reasoning = self.evaluate_with_llm_judge(case, generated_letter)
        
        if letter_score < 0.8:
            # If the judge hates it, treat the reasoning as an error
            letter_errors = [f"LLM Judge Complaint: {judge_reasoning}"]
        else:
            letter_errors = []

        # 3. Calculate Overall Score
        overall_score = (
            vision_score * 0.2 +      # 20% Accuracy
            research_score * 0.3 +    # 30% Facts/Citations
            letter_score * 0.5        # 50% Quality/Tone (Judge)
        )
        
        duration = time.time() - start_time
        
        # Add the judge's reasoning to the metadata for debugging
        agent_metadata = research_metadata.copy()
        agent_metadata["judge_reasoning"] = judge_reasoning
        
        return EvaluationResult(
            case_id=case.case_id,
            timestamp=datetime.now().isoformat(),
            duration_seconds=round(duration, 3),
            success=overall_score >= 0.6,
            vision_score=round(vision_score, 3),
            research_score=round(research_score, 3),
            letter_score=round(letter_score, 3),
            overall_score=round(overall_score, 3),
            vision_errors=vision_errors,
            research_errors=research_errors,
            letter_errors=letter_errors,
            generated_letter=generated_letter,
            agent_metadata=agent_metadata
        )
    
    def run_evaluation_suite(self, vision_agent, coordinator_team) -> List[EvaluationResult]:
        """Run full evaluation suite across all test cases."""
        results = []
        
        print("\n" + "="*70)
        print("🧪 RUNNING AGENT EVALUATION SUITE")
        print("="*70 + "\n")
        
        for i, case in enumerate(self.test_cases, 1):
            print(f"📋 Test Case {i}/{len(self.test_cases)}: {case.name}")
            print(f"   Description: {case.description}")
            print(f"   Provider: {case.insurance_provider}") # Visible confirmation
            
            try:
                test_image = self._get_test_image_path(case.case_id)
                
                # STRICT MODE
                if not test_image.exists():
                    raise FileNotFoundError(f"CRITICAL: Test image not found at {test_image}")

                print(f"   👁️  Running vision analysis on {test_image.name}")
                vision_output = vision_agent.analyze_bill(str(test_image))
                
                # Run coordinator with SPECIFIC PROVIDER
                generated_letter = coordinator_team.run(
                    vision_output,
                    insurance_provider=case.insurance_provider 
                )
                
                result = self.evaluate_case(case, generated_letter, vision_output)
                results.append(result)
                
                status = "✅ PASS" if result.success else "❌ FAIL"
                print(f"   {status} - Overall Score: {result.overall_score:.1%}")
                
                if not result.success:
                    all_errors = result.vision_errors + result.research_errors + result.letter_errors
                    for error in all_errors[:3]:
                        print(f"      ⚠️  {error}")
                
            except Exception as e:
                print(f"   ❌ ERROR: {str(e)}")
                # Add failed result to keep tracking
                results.append(EvaluationResult(
                    case_id=case.case_id, timestamp=datetime.now().isoformat(),
                    duration_seconds=0, success=False, vision_score=0, research_score=0, 
                    letter_score=0, overall_score=0, vision_errors=[str(e)], 
                    research_errors=[], letter_errors=[], generated_letter="", agent_metadata={}
                ))
            
            print()
        
        self._save_results(results)
        self._print_summary(results)
        return results
    
    def _save_results(self, results: List[EvaluationResult]):
        """Save results to JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.results_dir / f"evaluation_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump({"timestamp": timestamp, "total_cases": len(results), 
                      "results": [asdict(r) for r in results]}, f, indent=2)
        print(f"💾 Results saved to {results_file}")
    
    def _print_summary(self, results: List[EvaluationResult]):
        """Print summary."""
        if not results: return
        total = len(results)
        passed = sum(1 for r in results if r.success)
        
        print("="*70)
        print("📊 EVALUATION SUMMARY")
        print("="*70)
        print(f"Total Cases: {total}")
        print(f"Passed: {passed} ({passed/total:.1%})")
        print("="*70 + "\n")