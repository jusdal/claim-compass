"""
Observability system for Claim Compass agents.
Provides logging, tracing, and metrics collection.
"""

import logging
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum


class AgentPhase(Enum):
    """Agent execution phases for tracking."""
    VISION = "vision"
    POLICY_RESEARCH = "policy_research"
    WEB_RESEARCH = "web_research"
    LETTER_WRITING = "letter_writing"
    COORDINATION = "coordination"


@dataclass
class AgentMetric:
    """Structured metric for agent execution."""
    timestamp: str
    phase: str
    agent_name: str
    duration_seconds: float
    tokens_used: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ObservabilityManager:
    """
    Centralized observability for multi-agent system.
    Tracks execution times, success rates, and agent behavior.
    """
    
    def __init__(self, log_dir: str = "logs"):
        """
        Initialize observability manager.
        
        Args:
            log_dir: Directory for log files and metrics
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup structured logging
        self.logger = self._setup_logger()
        
        # Metrics storage
        self.metrics: list[AgentMetric] = []
        self.session_start = datetime.now()
        
        # Current trace context
        self.current_trace_id: Optional[str] = None
        self.current_span_stack: list[Dict[str, Any]] = []
        
    def _setup_logger(self) -> logging.Logger:
        """Configure structured logging with file and console handlers."""
        logger = logging.getLogger("claim_compass")
        logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        logger.handlers = []
        
        # File handler with JSON formatting
        file_handler = logging.FileHandler(
            self.log_dir / f"agent_execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def start_trace(self, trace_id: str):
        """Start a new execution trace."""
        self.current_trace_id = trace_id
        self.logger.info(f"🔍 TRACE START: {trace_id}")
        
    def end_trace(self):
        """End current execution trace."""
        if self.current_trace_id:
            self.logger.info(f"✅ TRACE END: {self.current_trace_id}")
            self._save_metrics()
            self.current_trace_id = None
    
    def start_span(self, phase: AgentPhase, agent_name: str, metadata: Optional[Dict] = None):
        """
        Start a new span (agent execution phase).
        
        Args:
            phase: The agent phase being executed
            agent_name: Name of the agent
            metadata: Additional context (e.g., input size, query)
        """
        span = {
            "phase": phase.value,
            "agent_name": agent_name,
            "start_time": time.time(),
            "metadata": metadata or {}
        }
        self.current_span_stack.append(span)
        
        self.logger.info(
            f"▶️  START [{phase.value}] Agent: {agent_name} | "
            f"Trace: {self.current_trace_id} | Meta: {json.dumps(metadata or {})}"
        )
        
    def end_span(self, success: bool = True, error: Optional[str] = None, 
                 tokens_used: Optional[int] = None, result_metadata: Optional[Dict] = None):
        """
        End current span and record metrics.
        
        Args:
            success: Whether the operation succeeded
            error: Error message if failed
            tokens_used: Number of tokens consumed (if applicable)
            result_metadata: Additional results (e.g., extracted codes, found evidence)
        """
        if not self.current_span_stack:
            self.logger.warning("⚠️  Attempted to end span with no active span")
            return
            
        span = self.current_span_stack.pop()
        duration = time.time() - span["start_time"]
        
        # Create metric
        metric = AgentMetric(
            timestamp=datetime.now().isoformat(),
            phase=span["phase"],
            agent_name=span["agent_name"],
            duration_seconds=round(duration, 3),
            tokens_used=tokens_used,
            success=success,
            error_message=error,
            metadata={**span["metadata"], **(result_metadata or {})}
        )
        self.metrics.append(metric)
        
        # Log completion
        status_emoji = "✅" if success else "❌"
        self.logger.info(
            f"{status_emoji} END [{span['phase']}] Agent: {span['agent_name']} | "
            f"Duration: {duration:.2f}s | Tokens: {tokens_used or 'N/A'} | "
            f"Success: {success}"
        )
        
        if error:
            self.logger.error(f"  ↳ Error: {error}")
        
        if result_metadata:
            self.logger.info(f"  ↳ Results: {json.dumps(result_metadata)}")
    
    def log_tool_call(self, tool_name: str, query: str, result_size: int):
        """Log tool invocations (RAG, Google Search, etc.)."""
        self.logger.info(
            f"🔧 TOOL CALL: {tool_name} | Query: '{query[:100]}...' | "
            f"Result Size: {result_size} chars"
        )
    
    def log_agent_decision(self, agent_name: str, decision: str, reasoning: str):
        """Log agent reasoning and decisions."""
        self.logger.info(
            f"🧠 DECISION [{agent_name}]: {decision} | Reasoning: {reasoning}"
        )
    
    def _save_metrics(self):
        """Save metrics to JSON file."""
        metrics_file = self.log_dir / f"metrics_{self.current_trace_id}.json"
        
        with open(metrics_file, 'w') as f:
            json.dump(
                {
                    "trace_id": self.current_trace_id,
                    "session_start": self.session_start.isoformat(),
                    "metrics": [asdict(m) for m in self.metrics]
                },
                f,
                indent=2
            )
        
        self.logger.info(f"💾 Metrics saved to {metrics_file}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary statistics."""
        if not self.metrics:
            return {"message": "No metrics collected yet"}
        
        total_duration = sum(m.duration_seconds for m in self.metrics)
        total_tokens = sum(m.tokens_used for m in self.metrics if m.tokens_used)
        success_rate = sum(1 for m in self.metrics if m.success) / len(self.metrics)
        
        phase_stats = {}
        for phase in AgentPhase:
            phase_metrics = [m for m in self.metrics if m.phase == phase.value]
            if phase_metrics:
                phase_stats[phase.value] = {
                    "count": len(phase_metrics),
                    "avg_duration": round(sum(m.duration_seconds for m in phase_metrics) / len(phase_metrics), 3),
                    "success_rate": sum(1 for m in phase_metrics if m.success) / len(phase_metrics)
                }
        
        return {
            "total_executions": len(self.metrics),
            "total_duration_seconds": round(total_duration, 2),
            "total_tokens_used": total_tokens,
            "overall_success_rate": round(success_rate * 100, 1),
            "phase_breakdown": phase_stats
        }
    
    def print_summary(self):
        """Print formatted execution summary."""
        summary = self.get_summary()
        
        print("\n" + "="*60)
        print("📊 EXECUTION SUMMARY")
        print("="*60)
        print(f"Total Executions: {summary.get('total_executions', 0)}")
        print(f"Total Duration: {summary.get('total_duration_seconds', 0)}s")
        print(f"Total Tokens: {summary.get('total_tokens_used', 0)}")
        print(f"Success Rate: {summary.get('overall_success_rate', 0)}%")
        
        if 'phase_breakdown' in summary:
            print("\nPhase Breakdown:")
            for phase, stats in summary['phase_breakdown'].items():
                print(f"  {phase}:")
                print(f"    - Executions: {stats['count']}")
                print(f"    - Avg Duration: {stats['avg_duration']}s")
                print(f"    - Success Rate: {round(stats['success_rate']*100, 1)}%")
        print("="*60 + "\n")


# Global observability instance
_obs_manager: Optional[ObservabilityManager] = None


def get_observability_manager() -> ObservabilityManager:
    """Get or create the global observability manager."""
    global _obs_manager
    if _obs_manager is None:
        _obs_manager = ObservabilityManager()
    return _obs_manager