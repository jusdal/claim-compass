"""
Agent Evaluation Suite for Claim Compass.
Tests agent performance on synthetic and real-world medical bills.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import re
import logging

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
                description="Patient received emergency care at out-of-network facility",
                input_bill_data="""
                Provider Name: Memorial Hospital Emergency Department
                Date of Service: 2024-10-15
                Total Billed Amount: $8,450.00
                Patient Responsibility: $7,200.00
                Insurance Paid: $1,250.00
                
                CPT Codes:
                - 99285: Emergency Department Visit (High Complexity) - $1,850.00
                - 70450: CT Head without Contrast - $3,200.00
                - 36415: Routine Venipuncture - $150.00
                - 80053: Comprehensive Metabolic Panel - $250.00
                
                Denial Information:
                - Is this a denial? Yes
                - Denial reason: Out-of-network provider
                - Denial code: OON-001
                """,
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
                description="Patient exceeded annual PT visit limit",
                input_bill_data="""
                Provider Name: HealthFirst Physical Therapy
                Date of Service: 2024-11-05
                Total Billed Amount: $285.00
                Patient Responsibility: $285.00
                Insurance Paid: $0.00
                
                CPT Codes:
                - 97110: Therapeutic Exercise - $95.00
                - 97112: Neuromuscular Re-education - $95.00
                - 97140: Manual Therapy - $95.00
                
                Denial Information:
                - Is this a denial? Yes
                - Denial reason: Benefit limit exceeded
                - Denial code: BEN-LIM-30
                
                Additional Details: This is visit #31 for 2024. Plan states 30 visits per year.
                """,
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
                description="Denied for experimental/investigational treatment",
                input_bill_data="""
                Provider Name: Cancer Treatment Center of Excellence
                Date of Service: 2024-09-20
                Total Billed Amount: $45,000.00
                Patient Responsibility: $45,000.00
                Insurance Paid: $0.00
                
                CPT Codes:
                - 96413: Chemotherapy Administration (IV Infusion) - $2,500.00
                - J9999: Not Otherwise Classified Drug (Investigational Immunotherapy) - $42,500.00
                
                Denial Information:
                - Is this a denial? Yes
                - Denial reason: Experimental/Investigational Treatment
                - Denial code: EXP-001
                
                Additional Details: Clinical trial NCT04567890. Patient has Stage IV melanoma.
                """,
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
        """
        Evaluate vision agent's extraction accuracy.
        
        Returns:
            (score, errors) where score is 0-1
        """
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
        
        # Check if amounts are present
        if "Total Billed Amount" in case.input_bill_data:
            if "billed" not in bill_data.lower() and "amount" not in bill_data.lower():
                errors.append("Total billed amount not extracted")
                score_components.append(0.0)
            else:
                score_components.append(1.0)
        
        # Check if denial info is present
        if "Denial Information" in case.input_bill_data:
            if "denial" not in bill_data.lower():
                errors.append("Denial information not extracted")
                score_components.append(0.0)
            else:
                score_components.append(1.0)
        
        final_score = sum(score_components) / len(score_components) if score_components else 0.0
        return final_score, errors
    
    def evaluate_research_quality(self, case: EvaluationCase, letter: str, 
                                   research_metadata: Dict) -> Tuple[float, List[str]]:
        """
        Evaluate research agent's evidence gathering.
        
        Returns:
            (score, errors) where score is 0-1
        """
        errors = []
        score_components = []
        
        # Check for No Surprises Act (if applicable)
        if case.expected_outputs.get("should_mention_no_surprises_act"):
            if "no surprises act" in letter.lower() or "NSA" in letter:
                score_components.append(1.0)
            else:
                errors.append("Should cite No Surprises Act for emergency OON care")
                score_components.append(0.0)
        
        # Check for policy citations
        if case.expected_outputs.get("should_cite_policy"):
            # Look for evidence of policy quotes or references
            has_policy_ref = any(phrase in letter.lower() for phrase in 
                                ["policy states", "coverage document", "benefit guide", "plan document"])
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
            if phrase_score < 0.7:
                missing = set(expected_phrases) - set(found_phrases)
                errors.append(f"Missing key concepts: {missing}")
        
        final_score = sum(score_components) / len(score_components) if score_components else 0.0
        return final_score, errors
    
    def evaluate_letter_quality(self, case: EvaluationCase, letter: str) -> Tuple[float, List[str]]:
        """
        Evaluate the quality of the generated appeal letter.
        
        Returns:
            (score, errors) where score is 0-1
        """
        errors = []
        score_components = []
        
        # Check structure (greeting, body, closing)
        has_greeting = any(word in letter for word in ["Dear", "To Whom"])
        has_closing = any(word in letter for word in ["Sincerely", "Respectfully", "Regards"])
        
        structure_score = (has_greeting + has_closing) / 2
        score_components.append(structure_score)
        
        if not has_greeting:
            errors.append("Missing professional greeting")
        if not has_closing:
            errors.append("Missing professional closing")
        
        # Check length (should be substantial but not excessive)
        word_count = len(letter.split())
        if word_count < 100:
            errors.append(f"Letter too short ({word_count} words)")
            score_components.append(0.3)
        elif word_count > 1000:
            errors.append(f"Letter too long ({word_count} words)")
            score_components.append(0.7)
        else:
            score_components.append(1.0)
        
        # Check for professional tone (no inflammatory language)
        inflammatory_words = ["outrageous", "ridiculous", "incompetent", "scam", "fraud"]
        if any(word in letter.lower() for word in inflammatory_words):
            errors.append("Letter contains inflammatory language")
            score_components.append(0.5)
        else:
            score_components.append(1.0)
        
        # Check for clear ask/action items
        has_clear_ask = any(phrase in letter.lower() for phrase in 
                           ["request", "ask that you", "reconsider", "appeal", "review"])
        if has_clear_ask:
            score_components.append(1.0)
        else:
            errors.append("Missing clear request for action")
            score_components.append(0.5)
        
        final_score = sum(score_components) / len(score_components) if score_components else 0.0
        return final_score, errors
    
    def evaluate_case(self, case: EvaluationCase, generated_letter: str, 
                     vision_output: str, research_metadata: Dict = None) -> EvaluationResult:
        """
        Evaluate a single test case.
        
        Args:
            case: The test case
            generated_letter: The final appeal letter
            vision_output: Output from vision agent
            research_metadata: Optional metadata from research agents
            
        Returns:
            EvaluationResult with scores and errors
        """
        start_time = time.time()
        research_metadata = research_metadata or {}
        
        # Evaluate each component
        vision_score, vision_errors = self.evaluate_vision_extraction(case, vision_output)
        research_score, research_errors = self.evaluate_research_quality(case, generated_letter, research_metadata)
        letter_score, letter_errors = self.evaluate_letter_quality(case, generated_letter)
        
        # Calculate overall score (weighted average)
        overall_score = (
            vision_score * 0.2 +      # 20% vision accuracy
            research_score * 0.4 +    # 40% research quality
            letter_score * 0.4        # 40% letter quality
        )
        
        duration = time.time() - start_time
        
        return EvaluationResult(
            case_id=case.case_id,
            timestamp=datetime.now().isoformat(),
            duration_seconds=round(duration, 3),
            success=overall_score >= 0.6,  # 60% threshold for success
            vision_score=round(vision_score, 3),
            research_score=round(research_score, 3),
            letter_score=round(letter_score, 3),
            overall_score=round(overall_score, 3),
            vision_errors=vision_errors,
            research_errors=research_errors,
            letter_errors=letter_errors,
            generated_letter=generated_letter,
            agent_metadata=research_metadata
        )
    
    def run_evaluation_suite(self, vision_agent, coordinator_team) -> List[EvaluationResult]:
        """
        Run full evaluation suite across all test cases.
        
        Args:
            vision_agent: Instance of VisionAgent
            coordinator_team: Instance of CoordinatorTeam
            
        Returns:
            List of EvaluationResults
        """
        results = []
        
        print("\n" + "="*70)
        print("🧪 RUNNING AGENT EVALUATION SUITE")
        print("="*70 + "\n")
        
        for i, case in enumerate(self.test_cases, 1):
            print(f"📋 Test Case {i}/{len(self.test_cases)}: {case.name}")
            print(f"   Description: {case.description}")
            print(f"   Tags: {', '.join(case.tags)}")
            
            try:
                # Get the test image path for this case
                test_image = self._get_test_image_path(case.case_id)
                
                if test_image.exists():
                    print(f"   👁️  Running vision analysis on {test_image.name}")
                    vision_output = vision_agent.analyze_bill(str(test_image))
                else:
                    print(f"   ⚠️  Test image not found: {test_image}, simulating vision output")
                    vision_output = case.input_bill_data
                
                # Run coordinator to generate letter
                generated_letter = coordinator_team.run(vision_output)
                
                # Evaluate
                result = self.evaluate_case(case, generated_letter, vision_output)
                results.append(result)
                
                # Print result
                status = "✅ PASS" if result.success else "❌ FAIL"
                print(f"   {status} - Overall Score: {result.overall_score:.1%}")
                print(f"   └─ Vision: {result.vision_score:.1%} | Research: {result.research_score:.1%} | Letter: {result.letter_score:.1%}")
                
                if not result.success:
                    all_errors = result.vision_errors + result.research_errors + result.letter_errors
                    for error in all_errors[:3]:  # Show first 3 errors
                        print(f"      ⚠️  {error}")
                
            except Exception as e:
                print(f"   ❌ ERROR: {str(e)}")
                import traceback
                traceback.print_exc()  # This will show the full error
                
                # Create failed result
                result = EvaluationResult(
                    case_id=case.case_id,
                    timestamp=datetime.now().isoformat(),
                    duration_seconds=0,
                    success=False,
                    vision_score=0,
                    research_score=0,
                    letter_score=0,
                    overall_score=0,
                    vision_errors=[str(e)],
                    research_errors=[],
                    letter_errors=[],
                    generated_letter="",
                    agent_metadata={}
                )
                results.append(result)
            
            print()
        
        # Save results
        self._save_results(results)
        
        # Print summary
        self._print_summary(results)
        
        return results
    
    def _save_results(self, results: List[EvaluationResult]):
        """Save evaluation results to JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.results_dir / f"evaluation_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(
                {
                    "timestamp": timestamp,
                    "total_cases": len(results),
                    "results": [asdict(r) for r in results]
                },
                f,
                indent=2
            )
        
        print(f"💾 Results saved to {results_file}")
    
    def _print_summary(self, results: List[EvaluationResult]):
        """Print evaluation summary statistics."""
        if not results:
            print("No results to summarize")
            return
        
        total = len(results)
        passed = sum(1 for r in results if r.success)
        avg_overall = sum(r.overall_score for r in results) / total
        avg_vision = sum(r.vision_score for r in results) / total
        avg_research = sum(r.research_score for r in results) / total
        avg_letter = sum(r.letter_score for r in results) / total
        
        print("="*70)
        print("📊 EVALUATION SUMMARY")
        print("="*70)
        print(f"Total Cases: {total}")
        print(f"Passed: {passed} ({passed/total:.1%})")
        print(f"Failed: {total - passed}")
        print()
        print("Average Scores:")
        print(f"  Overall:  {avg_overall:.1%}")
        print(f"  Vision:   {avg_vision:.1%}")
        print(f"  Research: {avg_research:.1%}")
        print(f"  Letter:   {avg_letter:.1%}")
        print("="*70 + "\n")