"""
Form API Endpoints for Murphy System

This module provides REST API endpoints for form submission.
All user interactions with Murphy start through these endpoints.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import logging

from .schemas import FormType
from .handlers import submit_form

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/forms", tags=["forms"])


@router.post("/plan-upload")
async def submit_plan_upload_form(form_data: Dict[str, Any]) -> JSONResponse:
    """
    Submit a plan upload form
    
    Upload an existing plan for expansion and validation.
    
    **Request Body:**
    - plan_document: Path to uploaded document (PDF, DOCX, TXT, MD)
    - plan_context: Business context for the plan
    - expansion_level: How much detail to add (minimal/moderate/comprehensive)
    - constraints: List of constraints (budget, timeline, resources)
    - validation_criteria: How to validate success
    - human_checkpoints: When to request human review
    
    **Returns:**
    - submission_id: Unique ID for tracking
    - status: Processing status
    - next_step: What happens next
    """
    try:
        result = submit_form(FormType.PLAN_UPLOAD, form_data)
        
        if result.success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=result.to_dict()
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=result.to_dict()
            )
            
    except Exception as e:
        logger.error(f"Error in plan upload endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/plan-generation")
async def submit_plan_generation_form(form_data: Dict[str, Any]) -> JSONResponse:
    """
    Submit a plan generation form
    
    Generate a new plan from a goal description.
    
    **Request Body:**
    - goal: What you want to accomplish (min 50 chars)
    - domain: Domain category (software_development, business_strategy, etc.)
    - timeline: When it needs to be done
    - budget: Budget in USD (optional)
    - team_size: Number of people available (optional)
    - success_criteria: How to measure success
    - known_constraints: Any limitations or requirements
    - risk_tolerance: How much risk is acceptable (low/medium/high)
    
    **Returns:**
    - submission_id: Unique ID for tracking
    - status: Processing status
    - next_step: What happens next
    """
    try:
        result = submit_form(FormType.PLAN_GENERATION, form_data)
        
        if result.success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=result.to_dict()
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=result.to_dict()
            )
            
    except Exception as e:
        logger.error(f"Error in plan generation endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/task-execution")
async def submit_task_execution_form(form_data: Dict[str, Any]) -> JSONResponse:
    """
    Submit a task execution form
    
    Execute a specific task from a plan.
    
    **Request Body:**
    - plan_id: ID of the plan this task belongs to
    - task_id: ID of the task to execute
    - execution_mode: How to execute (automatic/supervised/manual)
    - confidence_threshold: Minimum confidence to proceed (0.0-1.0)
    - additional_context: Any extra information (optional)
    
    **Returns:**
    - submission_id: Unique ID for tracking
    - status: Processing status
    - next_step: What happens next
    """
    try:
        result = submit_form(FormType.TASK_EXECUTION, form_data)
        
        if result.success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=result.to_dict()
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=result.to_dict()
            )
            
    except Exception as e:
        logger.error(f"Error in task execution endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/validation")
async def submit_validation_form(form_data: Dict[str, Any]) -> JSONResponse:
    """
    Submit a validation form
    
    Validate Murphy's output for a task.
    
    **Request Body:**
    - task_id: ID of the task being validated
    - output_id: ID of the output to validate
    - validation_result: Outcome (approved/approved_with_changes/rejected)
    - quality_score: Quality rating (0-10)
    - feedback: What was good/bad
    - corrections: Specific corrections made (optional)
    
    **Returns:**
    - submission_id: Unique ID for tracking
    - status: Processing status
    - next_step: What happens next
    """
    try:
        result = submit_form(FormType.VALIDATION, form_data)
        
        if result.success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=result.to_dict()
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=result.to_dict()
            )
            
    except Exception as e:
        logger.error(f"Error in validation endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/correction")
async def submit_correction_form(form_data: Dict[str, Any]) -> JSONResponse:
    """
    Submit a correction form
    
    Capture corrections for training Murphy.
    
    **Request Body:**
    - task_id: ID of the task being corrected
    - output_id: ID of the output being corrected
    - correction_type: Types of corrections (factual_error, logic_error, etc.)
    - original_output: Murphy's original output (auto-filled)
    - corrected_output: Your corrected version
    - correction_rationale: Why you made these changes
    - severity: How serious was the error (minor/moderate/major/critical)
    
    **Returns:**
    - submission_id: Unique ID for tracking
    - status: Processing status
    - next_step: What happens next (training)
    """
    try:
        result = submit_form(FormType.CORRECTION, form_data)
        
        if result.success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=result.to_dict()
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=result.to_dict()
            )
            
    except Exception as e:
        logger.error(f"Error in correction endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/submission/{submission_id}")
async def get_submission_status(submission_id: str) -> JSONResponse:
    """
    Get status of a form submission
    
    Track the progress of a submitted form.
    
    **Path Parameters:**
    - submission_id: Unique submission ID
    
    **Returns:**
    - submission_id: The submission ID
    - status: Current status
    - progress: Progress information
    - results: Results if complete
    """
    try:
        # TODO: Implement submission status tracking
        # This will query the execution engine for status
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                'submission_id': submission_id,
                'status': 'not_implemented',
                'message': 'Status tracking will be implemented in execution engine'
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting submission status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/health")
async def health_check() -> JSONResponse:
    """
    Health check endpoint
    
    Verify the forms API is operational.
    
    **Returns:**
    - status: API status
    - timestamp: Current timestamp
    """
    from datetime import datetime
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            'status': 'healthy',
            'service': 'murphy-forms-api',
            'timestamp': datetime.now().isoformat()
        }
    )