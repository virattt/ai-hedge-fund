"""
Service for managing flow runs and cycles in the database.
"""
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from app.backend.database.models import HedgeFundFlowRun, HedgeFundFlowRunCycle, HedgeFundFlow
from app.backend.repositories.flow_run_repository import FlowRunRepository
from app.backend.repositories.flow_repository import FlowRepository
from app.backend.models.schemas import FlowRunStatus

logger = logging.getLogger(__name__)


class FlowRunService:
    """Service for managing flow runs and cycles."""
    
    def __init__(self, db: Session):
        self.db = db
        self.flow_run_repo = FlowRunRepository(db)
        self.flow_repo = FlowRepository(db)
    
    def get_or_create_cli_flow(self) -> HedgeFundFlow:
        """
        Get or create a default 'CLI' flow for command-line executions.
        
        Returns:
            HedgeFundFlow instance for CLI runs
        """
        # Look for existing CLI flow
        cli_flows = self.flow_repo.get_flows_by_name("CLI Executions")
        if cli_flows:
            return cli_flows[0]
        
        # Create a new CLI flow
        cli_flow = self.flow_repo.create_flow(
            name="CLI Executions",
            description="Default flow for command-line hedge fund executions",
            nodes=[],  # Empty nodes for CLI
            edges=[],  # Empty edges for CLI
            is_template=False
        )
        return cli_flow
    
    def create_or_get_flow_run(
        self,
        flow_id: Optional[int] = None,
        request_data: Optional[Dict[str, Any]] = None
    ) -> Optional[HedgeFundFlowRun]:
        """
        Create a new flow run or get existing one.
        
        Args:
            flow_id: Optional flow ID. If None, creates/uses a default CLI flow.
            request_data: Optional request data to store
        
        Returns:
            HedgeFundFlowRun instance or None on error
        """
        try:
            if flow_id is None:
                # For CLI runs, create or get the default CLI flow
                cli_flow = self.get_or_create_cli_flow()
                flow_id = cli_flow.id
            
            # Check if there's an active run for this flow
            active_run = self.flow_run_repo.get_active_flow_run(flow_id)
            if active_run:
                return active_run
            
            # Create a new flow run
            flow_run = self.flow_run_repo.create_flow_run(flow_id, request_data)
            
            # Mark as in progress
            flow_run.status = FlowRunStatus.IN_PROGRESS.value
            flow_run.started_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(flow_run)
            
            return flow_run
        except Exception as e:
            logger.error(f"Error creating flow run: {e}", exc_info=True)
            self.db.rollback()
            return None
    
    def create_cycle(
        self,
        flow_run_id: int,
        cycle_number: Optional[int] = None,
        trigger_reason: Optional[str] = None,
        market_conditions: Optional[Dict[str, Any]] = None
    ) -> Optional[HedgeFundFlowRunCycle]:
        """
        Create a new cycle for a flow run.
        
        Args:
            flow_run_id: The flow run ID
            cycle_number: Optional cycle number. If None, auto-increments.
            trigger_reason: Optional reason for triggering this cycle
            market_conditions: Optional market conditions snapshot
        
        Returns:
            HedgeFundFlowRunCycle instance or None on error
        """
        try:
            # Get the next cycle number if not provided
            if cycle_number is None:
                max_cycle = (
                    self.db.query(func.max(HedgeFundFlowRunCycle.cycle_number))
                    .filter(HedgeFundFlowRunCycle.flow_run_id == flow_run_id)
                    .scalar()
                )
                cycle_number = (max_cycle or 0) + 1
            
            cycle = HedgeFundFlowRunCycle(
                flow_run_id=flow_run_id,
                cycle_number=cycle_number,
                started_at=datetime.utcnow(),
                status="IN_PROGRESS",
                trigger_reason=trigger_reason,
                market_conditions=market_conditions
            )
            
            self.db.add(cycle)
            self.db.commit()
            self.db.refresh(cycle)
            
            return cycle
        except Exception as e:
            logger.error(f"Error creating cycle: {e}", exc_info=True)
            self.db.rollback()
            return None
    
    def update_cycle_with_results(
        self,
        cycle_id: int,
        analyst_signals: Optional[Dict[str, Any]] = None,
        trading_decisions: Optional[Dict[str, Any]] = None,
        portfolio_snapshot: Optional[Dict[str, Any]] = None,
        executed_trades: Optional[Dict[str, Any]] = None,
        performance_metrics: Optional[Dict[str, Any]] = None,
        llm_calls_count: Optional[int] = None,
        api_calls_count: Optional[int] = None,
        estimated_cost: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[HedgeFundFlowRunCycle]:
        """
        Update a cycle with analysis results.
        
        Args:
            cycle_id: The cycle ID to update
            analyst_signals: Analyst signals data
            trading_decisions: Trading decisions from portfolio manager
            portfolio_snapshot: Portfolio state after cycle
            executed_trades: Actual trades executed
            performance_metrics: Performance metrics for this cycle
            llm_calls_count: Number of LLM calls
            api_calls_count: Number of API calls
            estimated_cost: Estimated cost in USD
            error_message: Error message if cycle failed
        
        Returns:
            Updated HedgeFundFlowRunCycle instance or None on error
        """
        try:
            cycle = self.db.query(HedgeFundFlowRunCycle).filter(
                HedgeFundFlowRunCycle.id == cycle_id
            ).first()
            
            if not cycle:
                logger.error(f"Cycle {cycle_id} not found")
                return None
            
            # Update fields if provided
            if analyst_signals is not None:
                cycle.analyst_signals = analyst_signals
            if trading_decisions is not None:
                cycle.trading_decisions = trading_decisions
            if portfolio_snapshot is not None:
                cycle.portfolio_snapshot = portfolio_snapshot
            if executed_trades is not None:
                cycle.executed_trades = executed_trades
            if performance_metrics is not None:
                cycle.performance_metrics = performance_metrics
            if llm_calls_count is not None:
                cycle.llm_calls_count = llm_calls_count
            if api_calls_count is not None:
                cycle.api_calls_count = api_calls_count
            if estimated_cost is not None:
                cycle.estimated_cost = estimated_cost
            if error_message is not None:
                cycle.error_message = error_message
                cycle.status = "ERROR"
            else:
                cycle.status = "COMPLETED"
                cycle.completed_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(cycle)
            
            return cycle
        except Exception as e:
            logger.error(f"Error updating cycle: {e}", exc_info=True)
            self.db.rollback()
            return None
    
    def complete_flow_run(
        self,
        flow_run_id: int,
        final_portfolio: Optional[Dict[str, Any]] = None,
        results: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> Optional[HedgeFundFlowRun]:
        """
        Mark a flow run as complete.
        
        Args:
            flow_run_id: The flow run ID
            final_portfolio: Final portfolio state
            results: Final results
            error_message: Error message if run failed
        
        Returns:
            Updated HedgeFundFlowRun instance or None on error
        """
        try:
            flow_run = self.flow_run_repo.get_flow_run_by_id(flow_run_id)
            if not flow_run:
                return None
            
            if error_message:
                status = FlowRunStatus.ERROR
            else:
                status = FlowRunStatus.COMPLETE
            
            if final_portfolio:
                flow_run.final_portfolio = final_portfolio
            if results:
                flow_run.results = results
            
            self.flow_run_repo.update_flow_run(
                flow_run_id,
                status=status,
                error_message=error_message
            )
            
            return flow_run
        except Exception as e:
            logger.error(f"Error completing flow run: {e}", exc_info=True)
            self.db.rollback()
            return None

