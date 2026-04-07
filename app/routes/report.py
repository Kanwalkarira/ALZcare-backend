"""
Report generation routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks # type: ignore
from fastapi.responses import RedirectResponse
from typing import Optional
import uuid

from app.models.user import UserInDB, UserRole # type: ignore
from app.services.report_service import report_service # type: ignore
from app.services.firestore import firestore_service # type: ignore
from app.services.storage_service import storage_service # type: ignore
from app.dependencies.auth import require_role # type: ignore

router = APIRouter(prefix="/reports", tags=["Reports"])

# Role dependencies
require_doctor = require_role([UserRole.doctor.value, UserRole.admin.value])

async def generate_report_background_task(report_id: str, patient_id: str, doctor_name: str, timeframe: str):
    try:
        # Update status to generating
        await firestore_service.update_report_record(report_id, {"status": "generating"})
        
        pdf_buffer = await report_service.generate_patient_report(
            patient_id=patient_id,
            doctor_name=doctor_name,
            timeframe=timeframe
        )
        
        # Upload to Storage
        download_url = await storage_service.upload_report_pdf(pdf_buffer.getvalue(), report_id)
        
        if download_url:
            await firestore_service.update_report_record(report_id, {
                "status": "completed",
                "download_url": download_url
            })
        else:
            raise Exception("Failed to upload report PDF to storage")
            
    except Exception as e:
        await firestore_service.update_report_record(report_id, {
            "status": "error",
            "error": str(e)
        })

@router.post("/patients/{patient_id}/generate", status_code=status.HTTP_200_OK)
async def generate_report(
    patient_id: str,
    background_tasks: BackgroundTasks,
    timeframe: str = "monthly",
    current_user: UserInDB = Depends(require_doctor)
):
    """
    Generate a PDF report for a patient.
    **Doctor only.**
    
    - **timeframe**: 'weekly' or 'monthly' (default: 'monthly')
    """
    if timeframe not in ["weekly", "monthly"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid timeframe. Must be 'weekly' or 'monthly'."
        )

    report_id = str(uuid.uuid4())
    
    # Create persistent record in Firestore
    await firestore_service.create_report_record(
        report_id=report_id,
        patient_id=patient_id,
        timeframe=timeframe,
        doctor_name=current_user.name
    )
    
    background_tasks.add_task(
        generate_report_background_task,
        report_id=report_id,
        patient_id=patient_id,
        doctor_name=current_user.name,
        timeframe=timeframe
    )
    
    return {"status": "generating", "report_id": report_id}

@router.get("/{report_id}/status")
async def get_report_status(report_id: str):
    """Poll for report generation completion."""
    report = await firestore_service.get_report_record(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    r_status = report.get("status")
    if r_status == "error":
        return {"status": r_status, "error": report.get("error")}
    return {"status": r_status}

@router.get("/{report_id}/download")
async def download_report(report_id: str):
    """Download the generated report PDF."""
    report = await firestore_service.get_report_record(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    if report.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Report is not completed yet")
        
    download_url = report.get("download_url")
    if not download_url:
         raise HTTPException(status_code=500, detail="Download URL missing for completed report")

    # Redirect directly to the storage public URL
    return RedirectResponse(url=download_url)
